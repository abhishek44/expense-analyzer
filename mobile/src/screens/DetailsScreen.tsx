import React, { useEffect, useState } from 'react';
import {
    View,
    Text,
    StyleSheet,
    TextInput,
    ScrollView,
    ActivityIndicator,
    Alert,
    KeyboardAvoidingView,
    Platform,
    TouchableOpacity, // Keep TouchableOpacity as it's used for the review button
} from 'react-native';
import { Picker } from '@react-native-picker/picker';
import { NativeStackNavigationProp } from '@react-navigation/native-stack';
import { RouteProp } from '@react-navigation/native';
import { FilesStackParamList } from '../navigation/AppNavigator';
import { colors, spacing, borderRadius } from '../theme/colors';
import { api, Transaction, Category } from '../api/client';

type Props = {
    navigation: NativeStackNavigationProp<FilesStackParamList, 'Details'>;
    route: RouteProp<FilesStackParamList, 'Details'>;
};



export default function DetailsScreen({ navigation, route }: Props) {
    const { id } = route.params;
    const [transaction, setTransaction] = useState<Transaction | null>(null);
    const [loading, setLoading] = useState(true);
    const [submitting, setSubmitting] = useState(false);

    // Form state
    const [categories, setCategories] = useState<Category[]>([]);
    const [selectedCategoryId, setSelectedCategoryId] = useState<string>('');
    const [categoryName, setCategoryName] = useState(''); // Fallback for display or legacy
    const [notes, setNotes] = useState('');

    useEffect(() => {
        loadData();
    }, [id]);

    const loadData = async () => {
        try {
            setLoading(true);
            const [trxData, catsData] = await Promise.all([
                api.getTransaction(id),
                api.getCategories() // Fetch all or filter? For review, maybe all.
            ]);

            setCategories(catsData);
            setTransaction(trxData);

            // Pre-fill
            if (trxData.category_id) {
                setSelectedCategoryId(trxData.category_id);
                // Find name
                const cat = catsData.find(c => c.id === trxData.category_id);
                if (cat) setCategoryName(cat.name);
            } else if (trxData.Category) {
                // Try to find by name
                const cat = catsData.find(c => c.name === trxData.Category);
                if (cat) {
                    setSelectedCategoryId(cat.id);
                    setCategoryName(cat.name);
                } else {
                    // Legacy text only?
                    setCategoryName(trxData.Category);
                }
            }

            if (trxData.Notes) setNotes(trxData.Notes);
            else setNotes(trxData.Details || '');
        } catch (e) {
            Alert.alert('Error', 'Failed to load data');
            console.error(e);
        } finally {
            setLoading(false);
        }
    };

    const handleReview = async () => {
        setSubmitting(true);
        try {
            // Find category name from ID
            const selectedCat = categories.find(c => c.id === selectedCategoryId);
            const catName = selectedCat ? selectedCat.name : categoryName;

            const result = await api.reviewTransaction(id, {
                Category: catName,
                categoryId: selectedCategoryId,
                Notes: notes,
            });

            if (result.success) {
                navigation.goBack();
            } else {
                Alert.alert('Error', 'Failed to review transaction');
            }
        } catch (e) {
            Alert.alert('Error', 'Failed to review transaction');
            console.error(e);
        } finally {
            setSubmitting(false);
        }
    };

    if (loading) {
        return (
            <View style={styles.centered}>
                <ActivityIndicator size="large" color={colors.primary} />
            </View>
        );
    }

    if (!transaction) {
        return (
            <View style={styles.centered}>
                <Text style={styles.errorText}>Transaction not found</Text>
            </View>
        );
    }

    const isPending = transaction.review_status !== 'reviewed';

    return (
        <KeyboardAvoidingView
            style={styles.container}
            behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
            keyboardVerticalOffset={Platform.OS === 'ios' ? 100 : 80}
        >
            <ScrollView style={styles.scrollView} contentContainerStyle={styles.content}>
                {/* Transaction Info Card */}
                <View style={styles.card}>
                    <Text style={styles.cardTitle}>Transaction Info</Text>
                    <View style={styles.infoRow}>
                        <Text style={styles.infoLabel}>Date</Text>
                        <Text style={styles.infoValue}>{transaction.Date || '-'}</Text>
                    </View>
                    <View style={styles.infoRow}>
                        <Text style={styles.infoLabel}>Amount</Text>
                        <Text style={[styles.infoValueBold, transaction.Debit ? styles.debitText : styles.creditText]}>
                            {transaction.Debit ? `- ₹${transaction.Debit.toLocaleString()}` : transaction.Credit ? `+ ₹${transaction.Credit.toLocaleString()}` : '₹0'}
                        </Text>
                    </View>
                    <View style={styles.infoRow}>
                        <Text style={styles.infoLabel}>Type</Text>
                        <Text style={styles.infoValue}>
                            {transaction.Debit ? 'Debit' : 'Credit'}
                        </Text>
                    </View>
                    <View style={styles.infoRow}>
                        <Text style={styles.infoLabel}>Account Type</Text>
                        <Text style={styles.infoValue}>
                            {transaction.Account_type || '-'}
                        </Text>
                    </View>
                    <View style={styles.infoRow}>
                        <Text style={styles.infoLabel}>Account</Text>
                        <Text style={styles.infoValue}>
                            {transaction.Account_name || '-'}
                        </Text>
                    </View>
                    <View style={styles.infoRowFull}>
                        <Text style={styles.infoLabel}>Details</Text>
                        <Text style={styles.infoValueWrap}>
                            {transaction.Details || '-'}
                        </Text>
                    </View>
                </View>

                <View style={styles.card}>
                    <Text style={styles.cardTitle}>Review Transaction</Text>

                    <View style={styles.formFieldFull}>
                        <Text style={styles.fieldLabel}>Category</Text>
                        <View style={styles.pickerContainer}>
                            <Picker
                                selectedValue={selectedCategoryId}
                                onValueChange={(itemValue) => {
                                    setSelectedCategoryId(itemValue);
                                    // Also update name for display
                                    const cat = categories.find(c => c.id === itemValue);
                                    if (cat) setCategoryName(cat.name);
                                }}
                                style={styles.picker}
                            >
                                <Picker.Item label="- Select Category -" value="" />
                                {categories.map((cat) => (
                                    <Picker.Item key={cat.id} label={cat.name} value={cat.id} />
                                ))}
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
                            numberOfLines={3}
                        />
                    </View>
                </View>

                <TouchableOpacity
                    style={styles.deleteButton}
                    onPress={() => {
                        Alert.alert(
                            'Delete Transaction',
                            'Are you sure you want to delete this transaction?',
                            [
                                { text: 'Cancel', style: 'cancel' },
                                {
                                    text: 'Delete',
                                    style: 'destructive',
                                    onPress: async () => {
                                        try {
                                            const res = await api.deleteTransaction(id);
                                            if (res.success) navigation.goBack();
                                            else Alert.alert('Error', res.message);
                                        } catch (e) { Alert.alert('Error', 'Failed to delete'); }
                                    }
                                }
                            ]
                        );
                    }}
                >
                    <Text style={styles.deleteButtonText}>Delete Transaction</Text>
                </TouchableOpacity>

            </ScrollView>

            <View style={styles.footer}>
                <TouchableOpacity
                    style={[styles.approveButton, submitting && styles.buttonDisabled]}
                    onPress={handleReview}
                    disabled={submitting}
                >
                    {submitting ? (
                        <ActivityIndicator color={colors.white} />
                    ) : (
                        <>
                            <Text style={styles.approveIcon}>{isPending ? '✓' : '↻'}</Text>
                            <Text style={styles.approveText}>{isPending ? 'Review' : 'Update Review'}</Text>
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
    centered: {
        flex: 1,
        justifyContent: 'center',
        alignItems: 'center',
        backgroundColor: colors.backgroundDark,
    },
    errorText: {
        color: colors.danger,
        fontSize: 16,
    },
    scrollView: {
        flex: 1,
    },
    content: {
        padding: spacing.md,
        paddingBottom: 100,
    },
    card: {
        backgroundColor: colors.surfaceDark,
        borderRadius: borderRadius.lg,
        padding: spacing.md,
        marginBottom: spacing.md,
    },
    cardTitle: {
        color: colors.textSecondary,
        fontSize: 14,
        fontWeight: 'bold',
        marginBottom: spacing.md,
    },
    infoRow: {
        flexDirection: 'row',
        justifyContent: 'space-between',
        marginBottom: spacing.sm,
    },
    infoRowFull: {
        marginTop: spacing.sm,
    },
    infoLabel: {
        color: colors.textSecondary,
        fontSize: 14,
    },
    infoValue: {
        color: colors.textPrimary,
        fontSize: 14,
    },
    infoValueBold: {
        fontSize: 14,
        fontWeight: 'bold',
    },
    debitText: {
        color: colors.danger,
    },
    creditText: {
        color: colors.success,
    },
    infoValueWrap: {
        color: colors.textPrimary,
        fontSize: 14,
        marginTop: spacing.xs,
    },
    formFieldFull: {
        marginBottom: spacing.md,
    },
    fieldLabel: {
        color: colors.textSecondary,
        fontSize: 12,
        marginBottom: spacing.xs,
    },
    input: {
        backgroundColor: colors.backgroundDark,
        borderWidth: 1,
        borderColor: colors.borderDark,
        borderRadius: borderRadius.md,
        padding: spacing.sm,
        color: colors.textPrimary,
        fontSize: 14,
    },
    textArea: {
        height: 80,
        textAlignVertical: 'top',
    },
    categoryRow: {
        flexDirection: 'row',
        gap: spacing.xs,
    },
    categoryChip: {
        backgroundColor: colors.backgroundDark,
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
    reviewedBanner: {
        backgroundColor: colors.success + '20',
        borderRadius: borderRadius.md,
        padding: spacing.md,
        alignItems: 'center',
        marginTop: spacing.md,
    },
    reviewedText: {
        color: colors.success,
        fontSize: 16,
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
        position: 'absolute',
        bottom: 0,
        left: 0,
        right: 0,
        padding: spacing.md,
        paddingBottom: spacing.lg,
        backgroundColor: colors.backgroundDark,
        borderTopWidth: 1,
        borderTopColor: colors.borderDark,
    },
    approveButton: {
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
    approveIcon: {
        color: colors.white,
        fontSize: 18,
    },
    approveText: {
        color: colors.white,
        fontSize: 16,
        fontWeight: 'bold',
    },
    deleteButton: {
        backgroundColor: colors.danger + '20',
        borderRadius: borderRadius.lg,
        padding: spacing.md,
        alignItems: 'center',
        marginTop: spacing.sm,
        marginBottom: spacing.md,
    },
    deleteButtonText: {
        color: colors.danger,
        fontWeight: 'bold',
    }
});
