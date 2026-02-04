import React, { useState } from 'react';
import {
    View,
    Text,
    StyleSheet,
    Modal,
    TextInput,
    TouchableOpacity,
    ScrollView,
    KeyboardAvoidingView,
    Platform,
} from 'react-native';
import { colors, spacing, borderRadius } from '../theme/colors';
import { AccountType } from '../database/database';

interface AddAccountModalProps {
    visible: boolean;
    onClose: () => void;
    onSave: (account: {
        name: string;
        account_type: AccountType;
        opening_balance: number;
        currency: string;
    }) => Promise<void>;
    editAccount?: {
        id: string;
        name: string;
        account_type: AccountType;
        opening_balance: number;
        currency: string;
    } | null;
}

const ACCOUNT_TYPES: { label: string; value: AccountType }[] = [
    { label: 'Savings', value: AccountType.SAVINGS },
    { label: 'Current', value: AccountType.CURRENT },
    { label: 'Credit Card', value: AccountType.CREDIT_CARD },
    { label: 'Cash', value: AccountType.CASH },
    { label: 'Wallet', value: AccountType.WALLET },
    { label: 'Investment', value: AccountType.INVESTMENT },
];

export default function AddAccountModal({
    visible,
    onClose,
    onSave,
    editAccount,
}: AddAccountModalProps) {
    const [name, setName] = useState(editAccount?.name || '');
    const [amount, setAmount] = useState(
        editAccount?.opening_balance?.toString() || '0'
    );
    const [selectedType, setSelectedType] = useState<AccountType | null>(
        editAccount?.account_type || null
    );
    const [errors, setErrors] = useState<{ name?: string; amount?: string; type?: string }>({});
    const [saving, setSaving] = useState(false);

    // Reset form when modal becomes visible
    React.useEffect(() => {
        if (visible) {
            setName(editAccount?.name || '');
            setAmount(editAccount?.opening_balance?.toString() || '0');
            setSelectedType(editAccount?.account_type || null);
            setErrors({});
        }
    }, [visible, editAccount]);

    const validateForm = (): boolean => {
        const newErrors: { name?: string; amount?: string; type?: string } = {};

        // Validate name: min 2 chars after trimming
        const trimmedName = name.trim();
        if (trimmedName.length < 2) {
            newErrors.name = 'Name must be at least 2 characters';
        }

        // Validate amount: valid number, max 2 decimal places
        const amountValue = amount.trim();
        if (!/^-?\d*\.?\d{0,2}$/.test(amountValue) || isNaN(parseFloat(amountValue))) {
            newErrors.amount = 'Enter a valid amount (max 2 decimal places)';
        }

        // Validate type: must be selected
        if (!selectedType) {
            newErrors.type = 'Please select an account type';
        }

        setErrors(newErrors);
        return Object.keys(newErrors).length === 0;
    };

    const handleSave = async () => {
        if (!validateForm()) return;

        setSaving(true);
        try {
            await onSave({
                name: name.trim(),
                account_type: selectedType!,
                opening_balance: parseFloat(amount) || 0,
                currency: 'INR',
            });
            onClose();
        } catch (error) {
            console.error('Error saving account:', error);
        } finally {
            setSaving(false);
        }
    };

    return (
        <Modal
            visible={visible}
            transparent
            animationType="fade"
            onRequestClose={onClose}
        >
            <KeyboardAvoidingView
                behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
                style={styles.overlay}
            >
                <View style={styles.modalContainer}>
                    <View style={styles.modalContent}>
                        <Text style={styles.modalTitle}>
                            {editAccount ? 'Edit account' : 'Add new account'}
                        </Text>

                        {/* Initial Amount Input */}
                        <View style={styles.inputGroup}>
                            <Text style={styles.inputLabel}>Initial amount</Text>
                            <TextInput
                                style={[styles.input, errors.amount && styles.inputError]}
                                value={amount}
                                onChangeText={setAmount}
                                keyboardType="decimal-pad"
                                placeholder="0"
                                placeholderTextColor={colors.textSecondary}
                            />
                            {errors.amount && (
                                <Text style={styles.errorText}>{errors.amount}</Text>
                            )}
                            <Text style={styles.helperText}>
                                *Initial amount will not be reflected in analysis
                            </Text>
                        </View>

                        {/* Account Name Input */}
                        <View style={styles.inputGroup}>
                            <Text style={styles.inputLabel}>Name</Text>
                            <TextInput
                                style={[styles.input, errors.name && styles.inputError]}
                                value={name}
                                onChangeText={setName}
                                placeholder="Account name"
                                placeholderTextColor={colors.textSecondary}
                            />
                            {errors.name && (
                                <Text style={styles.errorText}>{errors.name}</Text>
                            )}
                        </View>

                        {/* Account Type Selection */}
                        <View style={styles.inputGroup}>
                            <Text style={styles.inputLabel}>Account Type</Text>
                            <ScrollView
                                horizontal
                                showsHorizontalScrollIndicator={false}
                                style={styles.typeContainer}
                            >
                                {ACCOUNT_TYPES.map((type) => (
                                    <TouchableOpacity
                                        key={type.value}
                                        style={[
                                            styles.typeButton,
                                            selectedType === type.value && styles.typeButtonSelected,
                                        ]}
                                        onPress={() => setSelectedType(type.value)}
                                    >
                                        <Text
                                            style={[
                                                styles.typeButtonText,
                                                selectedType === type.value && styles.typeButtonTextSelected,
                                            ]}
                                        >
                                            {type.label}
                                        </Text>
                                    </TouchableOpacity>
                                ))}
                            </ScrollView>
                            {errors.type && (
                                <Text style={styles.errorText}>{errors.type}</Text>
                            )}
                        </View>

                        {/* Buttons */}
                        <View style={styles.buttonContainer}>
                            <TouchableOpacity
                                style={styles.cancelButton}
                                onPress={onClose}
                                disabled={saving}
                            >
                                <Text style={styles.cancelButtonText}>CANCEL</Text>
                            </TouchableOpacity>
                            <TouchableOpacity
                                style={[styles.saveButton, saving && styles.buttonDisabled]}
                                onPress={handleSave}
                                disabled={saving}
                            >
                                <Text style={styles.saveButtonText}>
                                    {saving ? 'SAVING...' : 'SAVE'}
                                </Text>
                            </TouchableOpacity>
                        </View>
                    </View>
                </View>
            </KeyboardAvoidingView>
        </Modal>
    );
}

const styles = StyleSheet.create({
    overlay: {
        flex: 1,
        backgroundColor: 'rgba(0, 0, 0, 0.6)',
        justifyContent: 'center',
        alignItems: 'center',
    },
    modalContainer: {
        width: '90%',
        maxWidth: 400,
    },
    modalContent: {
        backgroundColor: colors.surfaceDark,
        borderRadius: borderRadius.lg,
        padding: spacing.lg,
        borderWidth: 1,
        borderColor: colors.borderDark,
    },
    modalTitle: {
        fontSize: 20,
        fontWeight: 'bold',
        color: colors.textPrimary,
        textAlign: 'center',
        marginBottom: spacing.lg,
    },
    inputGroup: {
        marginBottom: spacing.md,
    },
    inputLabel: {
        color: colors.textSecondary,
        fontSize: 14,
        marginBottom: spacing.xs,
    },
    input: {
        backgroundColor: '#4a5e4a',
        borderRadius: borderRadius.sm,
        paddingHorizontal: spacing.md,
        paddingVertical: spacing.sm,
        color: colors.textPrimary,
        fontSize: 16,
    },
    inputError: {
        borderWidth: 1,
        borderColor: colors.danger,
    },
    errorText: {
        color: colors.danger,
        fontSize: 12,
        marginTop: spacing.xs,
    },
    helperText: {
        color: colors.textSecondary,
        fontSize: 11,
        marginTop: spacing.xs,
        fontStyle: 'italic',
    },
    typeContainer: {
        flexDirection: 'row',
    },
    typeButton: {
        backgroundColor: colors.backgroundDark,
        paddingHorizontal: spacing.md,
        paddingVertical: spacing.sm,
        borderRadius: borderRadius.sm,
        marginRight: spacing.sm,
        borderWidth: 1,
        borderColor: colors.borderDark,
    },
    typeButtonSelected: {
        backgroundColor: colors.primary,
        borderColor: colors.primary,
    },
    typeButtonText: {
        color: colors.textSecondary,
        fontSize: 14,
    },
    typeButtonTextSelected: {
        color: colors.white,
        fontWeight: 'bold',
    },
    buttonContainer: {
        flexDirection: 'row',
        justifyContent: 'center',
        gap: spacing.md,
        marginTop: spacing.lg,
    },
    cancelButton: {
        backgroundColor: colors.backgroundDark,
        paddingHorizontal: spacing.xl,
        paddingVertical: spacing.sm,
        borderRadius: borderRadius.sm,
        borderWidth: 1,
        borderColor: colors.borderDark,
    },
    cancelButtonText: {
        color: colors.textPrimary,
        fontWeight: 'bold',
        fontSize: 14,
    },
    saveButton: {
        backgroundColor: '#4a5e4a',
        paddingHorizontal: spacing.xl,
        paddingVertical: spacing.sm,
        borderRadius: borderRadius.sm,
    },
    saveButtonText: {
        color: colors.textPrimary,
        fontWeight: 'bold',
        fontSize: 14,
    },
    buttonDisabled: {
        opacity: 0.6,
    },
});
