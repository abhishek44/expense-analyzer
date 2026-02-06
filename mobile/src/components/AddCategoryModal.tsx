import React, { useState } from 'react';
import {
    View,
    Text,
    StyleSheet,
    Modal,
    TextInput,
    TouchableOpacity,
    KeyboardAvoidingView,
    Platform,
    ScrollView,
} from 'react-native';
import { colors, spacing, borderRadius } from '../theme/colors';

interface AddCategoryModalProps {
    visible: boolean;
    onClose: () => void;
    onSave: (category: {
        id?: string;
        name: string;
        type: 'INCOME' | 'EXPENSE';
    }) => Promise<void>;
    category?: {
        id: string;
        name: string;
        type: 'INCOME' | 'EXPENSE';
    } | null;
}

const CATEGORY_TYPES: { label: string; value: 'INCOME' | 'EXPENSE' }[] = [
    { label: 'Expense', value: 'EXPENSE' },
    { label: 'Income', value: 'INCOME' },
];

export default function AddCategoryModal({
    visible,
    onClose,
    onSave,
    category,
}: AddCategoryModalProps) {
    const [name, setName] = useState('');
    const [selectedType, setSelectedType] = useState<'INCOME' | 'EXPENSE'>('EXPENSE');
    const [errors, setErrors] = useState<{ name?: string }>({});
    const [saving, setSaving] = useState(false);

    // Reset form when modal becomes visible or category changes
    React.useEffect(() => {
        if (visible) {
            if (category) {
                setName(category.name);
                setSelectedType(category.type);
            } else {
                setName('');
                setSelectedType('EXPENSE');
            }
            setErrors({});
        }
    }, [visible, category]);

    const validateForm = (): boolean => {
        const newErrors: { name?: string } = {};

        // Validate name: min 2 chars after trimming
        const trimmedName = name.trim();
        if (trimmedName.length < 2) {
            newErrors.name = 'Name must be at least 2 characters';
        }

        setErrors(newErrors);
        return Object.keys(newErrors).length === 0;
    };

    const handleSave = async () => {
        if (!validateForm()) return;

        setSaving(true);
        try {
            await onSave({
                id: category?.id,
                name: name.trim(),
                type: selectedType,
            });
            onClose();
        } catch (error) {
            console.error('Error saving category:', error);
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
                            {category ? 'Edit Category' : 'Add New Category'}
                        </Text>

                        {/* Name Input */}
                        <View style={styles.inputGroup}>
                            <Text style={styles.inputLabel}>Name</Text>
                            <TextInput
                                style={[styles.input, errors.name && styles.inputError]}
                                value={name}
                                onChangeText={setName}
                                placeholder="Category name"
                                placeholderTextColor={colors.textSecondary}
                                autoFocus={visible}
                            />
                            {errors.name && (
                                <Text style={styles.errorText}>{errors.name}</Text>
                            )}
                        </View>

                        {/* Type Selection */}
                        <View style={styles.inputGroup}>
                            <Text style={styles.inputLabel}>Type</Text>
                            <View style={styles.typeContainer}>
                                {CATEGORY_TYPES.map((type) => (
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
                            </View>
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
        backgroundColor: colors.backgroundDark,
        borderRadius: borderRadius.sm,
        paddingHorizontal: spacing.md,
        paddingVertical: spacing.sm,
        color: colors.textPrimary,
        fontSize: 16,
        borderWidth: 1,
        borderColor: colors.borderDark,
    },
    inputError: {
        borderColor: colors.danger,
    },
    errorText: {
        color: colors.danger,
        fontSize: 12,
        marginTop: spacing.xs,
    },
    typeContainer: {
        flexDirection: 'row',
    },
    typeButton: {
        backgroundColor: colors.backgroundDark,
        paddingHorizontal: spacing.xl,
        paddingVertical: spacing.sm,
        borderRadius: borderRadius.sm,
        marginRight: spacing.md,
        borderWidth: 1,
        borderColor: colors.borderDark,
        flex: 1,
        alignItems: 'center',
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
        flex: 1,
        alignItems: 'center',
    },
    cancelButtonText: {
        color: colors.textPrimary,
        fontWeight: 'bold',
        fontSize: 14,
    },
    saveButton: {
        backgroundColor: colors.primary,
        paddingHorizontal: spacing.xl,
        paddingVertical: spacing.sm,
        borderRadius: borderRadius.sm,
        flex: 1,
        alignItems: 'center',
    },
    saveButtonText: {
        color: colors.white,
        fontWeight: 'bold',
        fontSize: 14,
    },
    buttonDisabled: {
        opacity: 0.6,
    },
});
