import React, { useEffect, useState, useCallback } from 'react';
import {
    View,
    Text,
    StyleSheet,
    TouchableOpacity,
    FlatList,
    ActivityIndicator,
    Alert,
    RefreshControl,
    TextInput,
} from 'react-native';
import { Picker } from '@react-native-picker/picker';
import { NativeStackNavigationProp } from '@react-navigation/native-stack';
import { RouteProp, useFocusEffect } from '@react-navigation/native';
import { RootStackParamList } from '../navigation/AppNavigator';
import { colors, spacing, borderRadius } from '../theme/colors';
import { api, Transaction } from '../api/client';

type Props = {
    navigation: NativeStackNavigationProp<RootStackParamList, 'Transactions'>;
    route: RouteProp<RootStackParamList, 'Transactions'>;
};

type Filter = '' | 'pending' | 'reviewed';

export default function TransactionsScreen({ navigation, route }: Props) {
    const filename = route.params?.filename;
    const [transactions, setTransactions] = useState<Transaction[]>([]);
    const [loading, setLoading] = useState(true);
    const [refreshing, setRefreshing] = useState(false);
    const [filter, setFilter] = useState<Filter>('');

    const [accountName, setAccountName] = useState('');
    const [accountType, setAccountType] = useState('');
    const [showFilters, setShowFilters] = useState(false);
    const [filterOptions, setFilterOptions] = useState<{ accountNames: string[]; accountTypes: string[] }>({ accountNames: [], accountTypes: [] });

    useFocusEffect(
        useCallback(() => {
            loadStatements();
            loadFilterOptions();
        }, [filter])
    );

    const loadFilterOptions = async () => {
        try {
            const opts = await api.getFilterOptions();
            setFilterOptions(opts);
        } catch (e) {
            console.error('Failed to load filter options');
        }
    };

    const loadStatements = async () => {
        try {
            setLoading(true);
            const data = await api.getTransactions(
                filter || undefined,
                filename,
                accountName || undefined,
                accountType || undefined
            );
            setTransactions(data.data);
        } catch (e) {
            Alert.alert('Error', 'Failed to load transactions');
            console.error(e);
        } finally {
            setLoading(false);
            setRefreshing(false);
        }
    };

    const filters: { key: Filter; label: string }[] = [
        { key: '', label: 'All' },
        { key: 'pending', label: 'Pending' },
        { key: 'reviewed', label: 'Reviewed' },
    ];

    const renderStatement = ({ item }: { item: Transaction }) => (
        <TouchableOpacity
            style={styles.card}
            onPress={() => navigation.navigate('Details', { id: item.Id })}
        >
            <View style={styles.cardContent}>
                <View style={styles.cardLeft}>
                    <Text style={styles.cardTitle} numberOfLines={1}>
                        {item.Details || 'Transaction'}
                    </Text>
                    <Text style={styles.cardAmount}>
                        {item.Debit ? `- ₹${item.Debit.toLocaleString()}` : item.Credit ? `+ ₹${item.Credit.toLocaleString()}` : '₹0'}
                    </Text>
                    <Text style={styles.cardSubtitle} numberOfLines={1}>
                        {item.Account_name} • {item.Account_type}
                    </Text>
                </View>
                <View style={styles.cardRight}>
                    <View
                        style={[
                            styles.statusBadge,
                            item.review_status === 'reviewed'
                                ? styles.statusReviewed
                                : styles.statusPending,
                        ]}
                    >
                        <Text
                            style={[
                                styles.statusText,
                                item.review_status === 'reviewed'
                                    ? styles.statusTextReviewed
                                    : styles.statusTextPending,
                            ]}
                        >
                            {item.review_status}
                        </Text>
                    </View>
                    <Text style={styles.cardDate}>{item.Date || ''}</Text>
                </View>
            </View>
        </TouchableOpacity>
    );

    return (
        <View style={styles.container}>
            <View style={styles.header}>
                <View style={styles.filterRow}>
                    {filters.map((f) => (
                        <TouchableOpacity
                            key={f.key}
                            style={[
                                styles.filterChip,
                                filter === f.key && styles.filterChipActive,
                            ]}
                            onPress={() => setFilter(f.key)}
                        >
                            <Text
                                style={[
                                    styles.filterText,
                                    filter === f.key && styles.filterTextActive,
                                ]}
                            >
                                {f.label}
                            </Text>
                        </TouchableOpacity>
                    ))}
                    <TouchableOpacity
                        style={[styles.filterChip, showFilters && styles.filterChipActive]}
                        onPress={() => setShowFilters(!showFilters)}
                    >
                        <Text style={[styles.filterText, showFilters && styles.filterTextActive]}>Filters</Text>
                    </TouchableOpacity>
                </View>

                {showFilters && (
                    <View style={styles.advancedFilters}>
                        <View style={styles.pickerWrapper}>
                            <Text style={styles.label}>Account Name</Text>
                            <View style={styles.pickerContainer}>
                                <Picker
                                    selectedValue={accountName}
                                    onValueChange={(val) => setAccountName(val)}
                                    style={styles.picker}
                                >
                                    <Picker.Item label="All Accounts" value="" />
                                    {filterOptions.accountNames.map(n => (
                                        <Picker.Item key={n} label={n} value={n} />
                                    ))}
                                </Picker>
                            </View>
                        </View>

                        <View style={styles.pickerWrapper}>
                            <Text style={styles.label}>Account Type</Text>
                            <View style={styles.pickerContainer}>
                                <Picker
                                    selectedValue={accountType}
                                    onValueChange={(val) => setAccountType(val)}
                                    style={styles.picker}
                                >
                                    <Picker.Item label="All Types" value="" />
                                    {filterOptions.accountTypes.map(t => (
                                        <Picker.Item key={t} label={t} value={t} />
                                    ))}
                                </Picker>
                            </View>
                        </View>

                        <TouchableOpacity style={styles.applyButton} onPress={() => loadStatements()}>
                            <Text style={styles.applyButtonText}>Apply Filters</Text>
                        </TouchableOpacity>
                    </View>
                )}
            </View>

            {loading && !refreshing ? (
                <View style={styles.centered}>
                    <ActivityIndicator size="large" color={colors.primary} />
                </View>
            ) : (
                <FlatList
                    data={transactions}
                    renderItem={renderStatement}
                    keyExtractor={(item) => item.Id.toString()}
                    contentContainerStyle={styles.list}
                    ListEmptyComponent={
                        <Text style={styles.emptyText}>No transactions found</Text>
                    }
                    refreshControl={
                        <RefreshControl
                            refreshing={refreshing}
                            onRefresh={() => {
                                setRefreshing(true);
                                loadStatements();
                            }}
                            tintColor={colors.primary}
                        />
                    }
                />
            )}
        </View>
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
    },
    filterRow: {
        flexDirection: 'row',
        padding: spacing.md,
        gap: spacing.sm,
    },
    filterChip: {
        paddingHorizontal: spacing.md,
        paddingVertical: spacing.sm,
        backgroundColor: colors.surfaceDark,
        borderRadius: borderRadius.full,
        borderWidth: 1,
        borderColor: colors.borderDark,
    },
    filterChipActive: {
        backgroundColor: colors.primary,
        borderColor: colors.primary,
    },
    filterText: {
        color: colors.textSecondary,
        fontSize: 14,
    },
    filterTextActive: {
        color: colors.white,
        fontWeight: 'bold',
    },
    list: {
        padding: spacing.md,
        paddingTop: 0,
    },
    card: {
        backgroundColor: colors.surfaceDark,
        borderRadius: borderRadius.lg,
        padding: spacing.md,
        marginBottom: spacing.md,
    },
    cardContent: {
        flexDirection: 'row',
        justifyContent: 'space-between',
    },
    cardLeft: {
        flex: 1,
        marginRight: spacing.md,
    },
    cardTitle: {
        color: colors.textPrimary,
        fontSize: 16,
        fontWeight: 'bold',
    },
    cardAmount: {
        color: colors.textSecondary,
        fontSize: 14,
        marginTop: spacing.xs,
    },
    cardRight: {
        alignItems: 'flex-end',
    },
    statusBadge: {
        paddingHorizontal: spacing.sm,
        paddingVertical: spacing.xs,
        borderRadius: borderRadius.sm,
    },
    statusPending: {
        backgroundColor: colors.warning + '30',
    },
    statusReviewed: {
        backgroundColor: colors.success + '30',
    },
    statusText: {
        fontSize: 12,
        fontWeight: 'bold',
    },
    statusTextPending: {
        color: colors.warning,
    },
    statusTextReviewed: {
        color: colors.success,
    },
    cardDate: {
        color: colors.textSecondary,
        fontSize: 12,
        marginTop: spacing.xs,
    },
    emptyText: {
        color: colors.textSecondary,
        textAlign: 'center',
        marginTop: spacing.xl,
        fontSize: 16,
    },
    header: {
        paddingBottom: spacing.sm,
    },
    advancedFilters: {
        paddingHorizontal: spacing.md,
        gap: spacing.sm,
    },
    input: {
        backgroundColor: colors.surfaceDark,
        borderRadius: borderRadius.md,
        padding: spacing.sm,
        color: colors.textPrimary,
        borderWidth: 1,
        borderColor: colors.borderDark,
    },
    applyButton: {
        backgroundColor: colors.primary,
        padding: spacing.sm,
        borderRadius: borderRadius.md,
        alignItems: 'center',
    },
    applyButtonText: {
        color: colors.white,
        fontWeight: 'bold',
    },
    pickerWrapper: {
        marginBottom: spacing.xs,
    },
    label: {
        color: colors.textSecondary,
        fontSize: 12,
        marginBottom: 4,
    },
    pickerContainer: {
        borderWidth: 1,
        borderColor: colors.borderDark,
        borderRadius: borderRadius.md,
        backgroundColor: colors.surfaceDark,
        overflow: 'hidden',
        height: 50,
        justifyContent: 'center',
    },
    picker: {
        color: colors.textPrimary,
        backgroundColor: colors.surfaceDark,
        marginLeft: -8, // Tweak to align text if needed
    },
    cardSubtitle: {
        color: colors.textSecondary,
        fontSize: 12,
        marginTop: 2,
    }
});
