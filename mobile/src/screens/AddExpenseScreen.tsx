import React, { useState } from 'react';
import {
    View,
    Text,
    StyleSheet,
    TouchableOpacity,
    TextInput,
    ScrollView,
    Alert,
    KeyboardAvoidingView,
    Platform,
    ActivityIndicator,
} from 'react-native';
import { Picker } from '@react-native-picker/picker';
import { NativeStackNavigationProp } from '@react-navigation/native-stack';
import { RootStackParamList } from '../navigation/AppNavigator';
import { colors, spacing, borderRadius } from '../theme/colors';
import { api, Category } from '../api/client';
import { validateDate, sanitizeAmount } from '../utils/validation';

type Props = {
    navigation: NativeStackNavigationProp<RootStackParamList, 'AddExpense'>;
};


const transactionTypes = ['Debit', 'Credit'];

export default function AddExpenseScreen({ navigation }: Props) {
    const [transactionDate, setTransactionDate] = useState(new Date().toISOString().split('T')[0]);
    const [transactionType, setTransactionType] = useState('Debit');
    const [amount, setAmount] = useState('');
    const [categories, setCategories] = useState<Category[]>([]);
    const [selectedCategoryId, setSelectedCategoryId] = useState<string>('');
    const [account, setAccount] = useState('');
    const [accountType, setAccountType] = useState('Savings');
    const [notes, setNotes] = useState('');
    const [submitting, setSubmitting] = useState(false);

    React.useEffect(() => {
        loadCategories();
    }, []);

    const loadCategories = async () => {
        try {
            const data = await api.getCategories();
            setCategories(data);
            if (data.length > 0) {
                setSelectedCategoryId(data[0].id);
            }
        } catch (e) {
            console.error('Failed to load categories', e);
        }
    };

    const handleSave = async () => {
        // Validate date
        if (!validateDate(transactionDate)) {
            Alert.alert('Error', 'Please enter a valid date (YYYY-MM-DD)');
            return;
        }

        // Validate and sanitize amount
        const sanitized = sanitizeAmount(amount);
        if (!sanitized || parseFloat(sanitized) === 0) {
            Alert.alert('Error', 'Please enter a valid amount');
            return;
        }

        if (!account) {
            Alert.alert('Error', 'Please enter an account');
            return;
        }

        setSubmitting(true);
        try {
            const result = await api.createTransaction({
                Date: transactionDate,
                Details: notes || 'Manual entry',
                Debit: transactionType === 'Debit' ? parseFloat(sanitized) : undefined,
                Credit: transactionType === 'Credit' ? parseFloat(sanitized) : undefined,
                Account_name: account,
                Account_type: accountType,
                Category: categories.find(c => c.id === selectedCategoryId)?.name || 'Manual',
                categoryId: selectedCategoryId,
                Notes: notes || undefined,
            });

            if (result.success) {
                Alert.alert('Success', 'Transaction saved!', [
                    { text: 'OK', onPress: () => navigation.goBack() },
                ]);
            } else {
                Alert.alert('Error', 'Failed to save transaction');
            }
        } catch (e) {
            Alert.alert('Error', 'Failed to save transaction');
            console.error(e);
        } finally {
            setSubmitting(false);
        }
    };

    return (
        <KeyboardAvoidingView
            style={styles.container}
            behavior={Platform.OS === 'ios' ? 'padding' : undefined}
        >
            <ScrollView style={styles.scrollView} contentContainerStyle={styles.content}>
                <View style={styles.formRow}>
                    <View style={styles.formField}>
                        <Text style={styles.fieldLabel}>Date</Text>
                        <TextInput
                            style={styles.input}
                            value={transactionDate}
                            onChangeText={setTransactionDate}
                            placeholder="YYYY-MM-DD"
                            placeholderTextColor={colors.textSecondary}
                        />
                    </View>
                    <View style={styles.formField}>
                        <Text style={styles.fieldLabel}>Type</Text>
                        <View style={styles.pickerContainer}>
                            <Picker
                                selectedValue={transactionType}
                                onValueChange={(itemValue) => setTransactionType(itemValue)}
                                style={styles.picker}
                            >
                                {transactionTypes.map((type) => (
                                    <Picker.Item key={type} label={type} value={type} />
                                ))}
                            </Picker>
                        </View>
                    </View>
                </View>

                <View style={styles.formFieldFull}>
                    <Text style={styles.fieldLabel}>Amount</Text>
                    <TextInput
                        style={styles.inputLarge}
                        value={amount}
                        onChangeText={setAmount}
                        keyboardType="numeric"
                        placeholder="0.00"
                        placeholderTextColor={colors.textSecondary}
                    />
                </View>

                <View style={styles.formRow}>
                    <View style={styles.formField}>
                        <Text style={styles.fieldLabel}>Category</Text>
                        <View style={styles.pickerContainer}>
                            <Picker
                                selectedValue={selectedCategoryId}
                                onValueChange={(itemValue) => setSelectedCategoryId(itemValue)}
                                style={styles.picker}
                            >
                                {categories.map((cat) => (
                                    <Picker.Item key={cat.id} label={cat.name} value={cat.id} />
                                ))}
                            </Picker>
                        </View>
                    </View>
                    <View style={styles.formField}>
                        <Text style={styles.fieldLabel}>Account</Text>
                        <TextInput
                            style={styles.input}
                            value={account}
                            onChangeText={setAccount}
                            placeholder="Cash, Bank..."
                            placeholderTextColor={colors.textSecondary}
                        />
                    </View>
                </View>

                <View style={styles.formFieldFull}>
                    <Text style={styles.fieldLabel}>Account Type</Text>
                    <View style={styles.pickerContainer}>
                        <Picker
                            selectedValue={accountType}
                            onValueChange={(itemValue) => setAccountType(itemValue)}
                            style={styles.picker}
                        >
                            <Picker.Item label="Savings" value="Savings" />
                            <Picker.Item label="Credit Card" value="Credit Card" />
                            <Picker.Item label="Current" value="Current" />
                        </Picker>
                    </View>
                </View>

                <View style={styles.formFieldFull}>
                    <Text style={styles.fieldLabel}>Notes</Text>
                    <TextInput
                        style={[styles.input, styles.textArea]}
                        value={notes}
                        onChangeText={setNotes}
                        placeholder="Optional notes..."
                        placeholderTextColor={colors.textSecondary}
                        multiline
                        numberOfLines={4}
                    />
                </View>
            </ScrollView>

            <View style={styles.footer}>
                <TouchableOpacity
                    style={[styles.saveButton, submitting && styles.buttonDisabled]}
                    onPress={handleSave}
                    disabled={submitting}
                >
                    {submitting ? (
                        <ActivityIndicator color={colors.white} />
                    ) : (
                        <>
                            <Text style={styles.saveIcon}>💾</Text>
                            <Text style={styles.saveText}>Save Transaction</Text>
                        </>
                    )}
                </TouchableOpacity>
            </View>
        </KeyboardAvoidingView>
    );
}

const styles = StyleSheet.create({
    container: {
        flex: 1,
        backgroundColor: colors.backgroundDark,
    },
    scrollView: {
        flex: 1,
    },
    content: {
        padding: spacing.md,
        paddingBottom: 100,
    },
    formRow: {
        flexDirection: 'row',
        gap: spacing.md,
        marginBottom: spacing.md,
    },
    formField: {
        flex: 1,
    },
    formFieldFull: {
        marginBottom: spacing.md,
    },
    fieldLabel: {
        color: colors.textPrimary,
        fontSize: 14,
        fontWeight: '500',
        marginBottom: spacing.sm,
    },
    input: {
        backgroundColor: colors.surfaceDark,
        borderWidth: 1,
        borderColor: colors.borderDark,
        borderRadius: borderRadius.md,
        padding: spacing.md,
        color: colors.textPrimary,
        fontSize: 16,
    },
    inputLarge: {
        backgroundColor: colors.surfaceDark,
        borderWidth: 1,
        borderColor: colors.borderDark,
        borderRadius: borderRadius.md,
        padding: spacing.md,
        color: colors.textPrimary,
        fontSize: 24,
        textAlign: 'center',
    },
    textArea: {
        height: 100,
        textAlignVertical: 'top',
    },
    typeSelector: {
        flexDirection: 'row',
        gap: spacing.sm,
    },
    typeOption: {
        flex: 1,
        backgroundColor: colors.surfaceDark,
        borderWidth: 1,
        borderColor: colors.borderDark,
        borderRadius: borderRadius.md,
        padding: spacing.sm,
        alignItems: 'center',
    },
    typeOptionActive: {
        borderColor: colors.primary,
        backgroundColor: colors.primary + '20',
    },
    typeText: {
        color: colors.textSecondary,
        fontSize: 14,
    },
    typeTextActive: {
        color: colors.primary,
        fontWeight: 'bold',
    },
    categoryGrid: {
        flexDirection: 'row',
        flexWrap: 'wrap',
        gap: spacing.xs,
    },
    categoryChip: {
        backgroundColor: colors.surfaceDark,
        borderWidth: 1,
        borderColor: colors.borderDark,
        borderRadius: borderRadius.sm,
        paddingHorizontal: spacing.sm,
        paddingVertical: spacing.xs,
    },
    categoryChipActive: {
        borderColor: colors.primary,
        backgroundColor: colors.primary + '20',
    },
    categoryText: {
        color: colors.textSecondary,
        fontSize: 12,
    },
    categoryTextActive: {
        color: colors.primary,
        fontWeight: 'bold',
    },
    pickerContainer: {
        borderWidth: 1,
        borderColor: colors.borderDark,
        borderRadius: borderRadius.md,
        backgroundColor: colors.surfaceDark,
        overflow: 'hidden',
    },
    picker: {
        color: colors.white,
        backgroundColor: colors.surfaceDark,
    },
    footer: {
        padding: spacing.md,
        paddingBottom: spacing.lg,
    },
    saveButton: {
        backgroundColor: colors.primary,
        borderRadius: borderRadius.lg,
        padding: spacing.md,
        flexDirection: 'row',
        justifyContent: 'center',
        alignItems: 'center',
        gap: spacing.sm,
    },
    buttonDisabled: {
        opacity: 0.7,
    },
    saveIcon: {
        fontSize: 18,
    },
    saveText: {
        color: colors.white,
        fontSize: 16,
        fontWeight: 'bold',
    },
});
