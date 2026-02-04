import React, { useState, useCallback } from 'react';
import {
    View,
    Text,
    StyleSheet,
    TouchableOpacity,
    ScrollView,
    ActivityIndicator,
    Alert,
    RefreshControl,
} from 'react-native';
import { NativeStackNavigationProp } from '@react-navigation/native-stack';
import { useFocusEffect } from '@react-navigation/native';
import { RootStackParamList } from '../navigation/AppNavigator';
import { colors, spacing, borderRadius } from '../theme/colors';
import { database, Account, AccountType } from '../database/database';
import AddAccountModal from '../components/AddAccountModal';

type Props = {
    navigation: NativeStackNavigationProp<RootStackParamList, 'Accounts'>;
};

// Get emoji icon based on account type
const getAccountIcon = (type: AccountType): string => {
    switch (type) {
        case AccountType.SAVINGS:
            return '🐷';
        case AccountType.CURRENT:
            return '🏦';
        case AccountType.CREDIT_CARD:
            return '💳';
        case AccountType.CASH:
            return '💵';
        case AccountType.WALLET:
            return '👛';
        case AccountType.INVESTMENT:
            return '📈';
        default:
            return '💰';
    }
};

// Format currency
const formatCurrency = (amount: number): string => {
    return `₹${amount.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
};

export default function AccountsScreen({ navigation }: Props) {
    const [accounts, setAccounts] = useState<Array<Account & { balance: number }>>([]);
    const [loading, setLoading] = useState(true);
    const [refreshing, setRefreshing] = useState(false);
    const [modalVisible, setModalVisible] = useState(false);
    const [editingAccount, setEditingAccount] = useState<Account | null>(null);
    const [menuVisible, setMenuVisible] = useState<string | null>(null);

    const loadAccounts = async () => {
        try {
            const accountsWithBalances = await database.getAccountsWithBalances();
            setAccounts(accountsWithBalances);
        } catch (error) {
            console.error('Error loading accounts:', error);
            Alert.alert('Error', 'Failed to load accounts');
        } finally {
            setLoading(false);
            setRefreshing(false);
        }
    };

    useFocusEffect(
        useCallback(() => {
            loadAccounts();
        }, [])
    );

    const onRefresh = () => {
        setRefreshing(true);
        loadAccounts();
    };

    const handleAddAccount = async (accountData: {
        name: string;
        account_type: AccountType;
        opening_balance: number;
        currency: string;
    }) => {
        try {
            if (editingAccount) {
                await database.updateAccount(editingAccount.id, accountData);
            } else {
                await database.createAccount({
                    ...accountData,
                    is_archived: 0,
                });
            }
            setEditingAccount(null);
            await loadAccounts();
        } catch (error) {
            console.error('Error saving account:', error);
            throw error;
        }
    };

    const handleEditAccount = (account: Account) => {
        setEditingAccount(account);
        setMenuVisible(null);
        setModalVisible(true);
    };

    const handleDeleteAccount = (account: Account) => {
        setMenuVisible(null);
        Alert.alert(
            'Delete Account',
            `Are you sure you want to delete "${account.name}"?`,
            [
                { text: 'Cancel', style: 'cancel' },
                {
                    text: 'Delete',
                    style: 'destructive',
                    onPress: async () => {
                        try {
                            await database.deleteAccount(account.id);
                            await loadAccounts();
                        } catch (error) {
                            console.error('Error deleting account:', error);
                            Alert.alert('Error', 'Failed to delete account');
                        }
                    },
                },
            ]
        );
    };

    const openAddModal = () => {
        setEditingAccount(null);
        setModalVisible(true);
    };

    const closeModal = () => {
        setModalVisible(false);
        setEditingAccount(null);
    };

    if (loading) {
        return (
            <View style={styles.loadingContainer}>
                <ActivityIndicator size="large" color={colors.primary} />
            </View>
        );
    }

    return (
        <View style={styles.container}>
            <ScrollView
                style={styles.scrollView}
                contentContainerStyle={styles.scrollContent}
                refreshControl={
                    <RefreshControl
                        refreshing={refreshing}
                        onRefresh={onRefresh}
                        tintColor={colors.primary}
                    />
                }
            >
                {accounts.length === 0 ? (
                    <View style={styles.emptyState}>
                        <Text style={styles.emptyStateIcon}>🏦</Text>
                        <Text style={styles.emptyStateText}>No accounts yet</Text>
                        <Text style={styles.emptyStateSubtext}>
                            Add your first account to get started
                        </Text>
                    </View>
                ) : (
                    accounts.map((account) => (
                        <View key={account.id} style={styles.accountCard}>
                            <View style={styles.accountInfo}>
                                <Text style={styles.accountIcon}>
                                    {getAccountIcon(account.account_type)}
                                </Text>
                                <View style={styles.accountDetails}>
                                    <Text style={styles.accountName}>{account.name}</Text>
                                    <Text style={styles.accountBalance}>
                                        Balance: {formatCurrency(account.balance)}
                                    </Text>
                                </View>
                            </View>
                            <TouchableOpacity
                                style={styles.menuButton}
                                onPress={() =>
                                    setMenuVisible(menuVisible === account.id ? null : account.id)
                                }
                            >
                                <Text style={styles.menuDots}>⋮</Text>
                            </TouchableOpacity>

                            {/* Dropdown Menu */}
                            {menuVisible === account.id && (
                                <View style={styles.dropdownMenu}>
                                    <TouchableOpacity
                                        style={styles.menuItem}
                                        onPress={() => handleEditAccount(account)}
                                    >
                                        <Text style={styles.menuItemText}>Edit</Text>
                                    </TouchableOpacity>
                                    <TouchableOpacity
                                        style={styles.menuItem}
                                        onPress={() => handleDeleteAccount(account)}
                                    >
                                        <Text style={[styles.menuItemText, styles.deleteText]}>
                                            Delete
                                        </Text>
                                    </TouchableOpacity>
                                </View>
                            )}
                        </View>
                    ))
                )}
            </ScrollView>

            {/* Add Account Button */}
            <TouchableOpacity style={styles.addButton} onPress={openAddModal}>
                <Text style={styles.addButtonIcon}>⊕</Text>
                <Text style={styles.addButtonText}>ADD NEW ACCOUNT</Text>
            </TouchableOpacity>

            {/* Add/Edit Account Modal */}
            <AddAccountModal
                visible={modalVisible}
                onClose={closeModal}
                onSave={handleAddAccount}
                editAccount={editingAccount}
            />
        </View>
    );
}

const styles = StyleSheet.create({
    container: {
        flex: 1,
        backgroundColor: colors.backgroundDark,
    },
    loadingContainer: {
        flex: 1,
        justifyContent: 'center',
        alignItems: 'center',
        backgroundColor: colors.backgroundDark,
    },
    scrollView: {
        flex: 1,
    },
    scrollContent: {
        padding: spacing.md,
        paddingBottom: 100, // Space for the add button
    },
    emptyState: {
        alignItems: 'center',
        justifyContent: 'center',
        paddingVertical: spacing.xl * 2,
    },
    emptyStateIcon: {
        fontSize: 48,
        marginBottom: spacing.md,
    },
    emptyStateText: {
        color: colors.textPrimary,
        fontSize: 18,
        fontWeight: 'bold',
    },
    emptyStateSubtext: {
        color: colors.textSecondary,
        fontSize: 14,
        marginTop: spacing.xs,
    },
    accountCard: {
        backgroundColor: colors.surfaceDark,
        borderRadius: borderRadius.lg,
        padding: spacing.md,
        marginBottom: spacing.md,
        flexDirection: 'row',
        alignItems: 'center',
        justifyContent: 'space-between',
        position: 'relative',
    },
    accountInfo: {
        flexDirection: 'row',
        alignItems: 'center',
        flex: 1,
    },
    accountIcon: {
        fontSize: 32,
        marginRight: spacing.md,
    },
    accountDetails: {
        flex: 1,
    },
    accountName: {
        color: colors.textPrimary,
        fontSize: 16,
        fontWeight: 'bold',
    },
    accountBalance: {
        color: colors.textSecondary,
        fontSize: 14,
        marginTop: spacing.xs,
    },
    menuButton: {
        padding: spacing.sm,
    },
    menuDots: {
        color: colors.textSecondary,
        fontSize: 20,
    },
    dropdownMenu: {
        position: 'absolute',
        right: spacing.md,
        top: spacing.md + 40,
        backgroundColor: colors.backgroundDark,
        borderRadius: borderRadius.sm,
        borderWidth: 1,
        borderColor: colors.borderDark,
        zIndex: 100,
        elevation: 5,
        shadowColor: '#000',
        shadowOffset: { width: 0, height: 2 },
        shadowOpacity: 0.25,
        shadowRadius: 4,
    },
    menuItem: {
        paddingHorizontal: spacing.lg,
        paddingVertical: spacing.sm,
    },
    menuItemText: {
        color: colors.textPrimary,
        fontSize: 14,
    },
    deleteText: {
        color: colors.danger,
    },
    addButton: {
        position: 'absolute',
        bottom: spacing.lg,
        left: spacing.lg,
        right: spacing.lg,
        backgroundColor: colors.surfaceDark,
        borderRadius: borderRadius.lg,
        paddingVertical: spacing.md,
        flexDirection: 'row',
        alignItems: 'center',
        justifyContent: 'center',
        borderWidth: 1,
        borderColor: colors.borderDark,
    },
    addButtonIcon: {
        color: colors.textPrimary,
        fontSize: 20,
        marginRight: spacing.sm,
    },
    addButtonText: {
        color: colors.textPrimary,
        fontSize: 14,
        fontWeight: 'bold',
    },
});
