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
    ScrollView,
    Platform,
} from 'react-native';
import { Picker } from '@react-native-picker/picker';
import { useFocusEffect } from '@react-navigation/native';
import { NativeStackNavigationProp } from '@react-navigation/native-stack';
import { RouteProp } from '@react-navigation/native';
import DateTimePicker, { DateTimePickerEvent } from '@react-native-community/datetimepicker';
import { FilesStackParamList } from '../navigation/AppNavigator';
import { colors, spacing, borderRadius } from '../theme/colors';
import { api, Transaction, Category } from '../api/client';

type Props = {
    navigation: NativeStackNavigationProp<FilesStackParamList, 'Transactions'>;
    route: RouteProp<FilesStackParamList, 'Transactions'>;
};

type Filter = '' | 'pending' | 'reviewed';

export default function TransactionsScreen({ navigation, route }: Props) {
    const filename = route.params?.filename;
    const [transactions, setTransactions] = useState<Transaction[]>([]);
    const [loading, setLoading] = useState(true);
    const [refreshing, setRefreshing] = useState(false);
    const [filter, setFilter] = useState<Filter>('');

    // Advanced filter state (applied values)
    const [accountName, setAccountName] = useState('');
    const [accountType, setAccountType] = useState('');
    const [categoryId, setCategoryId] = useState('');
    const [dateFrom, setDateFrom] = useState('');
    const [dateTo, setDateTo] = useState('');

    // Pending filter state (values in the panel before Apply)
    const [pendingAccountName, setPendingAccountName] = useState('');
    const [pendingAccountType, setPendingAccountType] = useState('');
    const [pendingCategoryId, setPendingCategoryId] = useState('');
    const [pendingDateFrom, setPendingDateFrom] = useState('');
    const [pendingDateTo, setPendingDateTo] = useState('');

    const [categories, setCategories] = useState<Category[]>([]);
    const [showFilters, setShowFilters] = useState(false);
    const [filterOptions, setFilterOptions] = useState<{ accountNames: string[]; accountTypes: string[] }>({ accountNames: [], accountTypes: [] });

    // Date picker modal state
    const [showDatePicker, setShowDatePicker] = useState(false);
    const [datePickerTarget, setDatePickerTarget] = useState<'from' | 'to'>('from');

    // Pagination state
    const PAGE_SIZE = 100;
    const [totalCount, setTotalCount] = useState(0);
    const [loadingMore, setLoadingMore] = useState(false);
    const currentSkipRef = React.useRef(0);

    useFocusEffect(
        useCallback(() => {
            loadFilterOptions();
        }, [])
    );

    useEffect(() => {
        // Reset pagination on filter change
        currentSkipRef.current = 0;
        setTransactions([]);
        loadStatements(false);
    }, [filter, filename, accountName, accountType, categoryId, dateFrom, dateTo]);

    // Scroll tracking
    const scrollOffset = React.useRef(0);

    const loadFilterOptions = async () => {
        try {
            const [opts, cats] = await Promise.all([
                api.getFilterOptions(),
                api.getCategories()
            ]);
            setFilterOptions(opts);
            setCategories(cats);

            if (accountName && !opts.accountNames.includes(accountName)) {
                setAccountName('');
            }
            if (accountType && !opts.accountTypes.includes(accountType)) {
                setAccountType('');
            }
        } catch (e) {
            console.error('Failed to load filter options');
        }
    };

    // Race condition tracking
    const requestRef = React.useRef(0);

    const loadStatements = async (append: boolean) => {
        const requestId = ++requestRef.current;
        try {
            if (!append) {
                setLoading(true);
                currentSkipRef.current = 0;
            } else {
                setLoadingMore(true);
            }

            const data = await api.getTransactions(
                filter || undefined,
                filename,
                accountName || undefined,
                accountType || undefined,
                categoryId || undefined,
                PAGE_SIZE,
                currentSkipRef.current,
                dateFrom || undefined,
                dateTo || undefined
            );

            // Ignore stale responses
            if (requestId === requestRef.current) {
                setTotalCount(data.total);
                if (append) {
                    setTransactions(prev => [...prev, ...data.data]);
                } else {
                    setTransactions(data.data);
                }
                currentSkipRef.current += data.data.length;
            }
        } catch (e) {
            if (requestId === requestRef.current) {
                Alert.alert('Error', 'Failed to load transactions');
                console.error(e);
            }
        } finally {
            if (requestId === requestRef.current) {
                setLoading(false);
                setRefreshing(false);
                setLoadingMore(false);
            }
        }
    };

    const handleLoadMore = () => {
        if (loadingMore || loading) return;
        if (transactions.length >= totalCount) return;
        loadStatements(true);
    };

    const filters: { key: Filter; label: string }[] = [
        { key: '', label: 'All' },
        { key: 'pending', label: 'Pending' },
        { key: 'reviewed', label: 'Reviewed' },
    ];

    // Active advanced filter count for badge
    const activeFilterCount = [accountName, accountType, categoryId, dateFrom, dateTo].filter(Boolean).length;

    // Sync pending state when opening the filter panel
    const openFilterPanel = () => {
        setPendingAccountName(accountName);
        setPendingAccountType(accountType);
        setPendingCategoryId(categoryId);
        setPendingDateFrom(dateFrom);
        setPendingDateTo(dateTo);
        setShowFilters(true);
    };

    const handleApplyFilters = () => {
        // Validate dates
        if (pendingDateFrom && pendingDateTo && pendingDateFrom > pendingDateTo) {
            Alert.alert('Invalid Date Range', '"From Date" cannot be after "To Date". Please correct the date range.');
            return;
        }
        setAccountName(pendingAccountName);
        setAccountType(pendingAccountType);
        setCategoryId(pendingCategoryId);
        setDateFrom(pendingDateFrom);
        setDateTo(pendingDateTo);
        setShowFilters(false);
    };

    const handleClearFilters = () => {
        setPendingAccountName('');
        setPendingAccountType('');
        setPendingCategoryId('');
        setPendingDateFrom('');
        setPendingDateTo('');
        setAccountName('');
        setAccountType('');
        setCategoryId('');
        setDateFrom('');
        setDateTo('');
        setShowFilters(false);
    };

    const removeFilter = (key: string) => {
        switch (key) {
            case 'accountName': setAccountName(''); break;
            case 'accountType': setAccountType(''); break;
            case 'categoryId': setCategoryId(''); break;
            case 'dateFrom': setDateFrom(''); break;
            case 'dateTo': setDateTo(''); break;
        }
    };

    // Format date for display: YYYY-MM-DD → DD MMM YYYY
    const formatDate = (dateStr: string): string => {
        if (!dateStr) return '';
        const d = new Date(dateStr + 'T00:00:00');
        return d.toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' });
    };

    // DateTimePicker handlers
    const openDatePicker = (target: 'from' | 'to') => {
        setDatePickerTarget(target);
        setShowDatePicker(true);
    };

    const onDateChange = (event: DateTimePickerEvent, selectedDate?: Date) => {
        setShowDatePicker(Platform.OS === 'ios'); // iOS keeps modal open
        if (event.type === 'dismissed') return;
        if (selectedDate) {
            const yyyy = selectedDate.getFullYear();
            const mm = String(selectedDate.getMonth() + 1).padStart(2, '0');
            const dd = String(selectedDate.getDate()).padStart(2, '0');
            const formatted = `${yyyy}-${mm}-${dd}`;
            if (datePickerTarget === 'from') setPendingDateFrom(formatted);
            else setPendingDateTo(formatted);
        }
    };

    // Build active filter tags
    const getFilterTags = () => {
        const tags: { label: string; key: string; icon: string }[] = [];
        if (accountName) tags.push({ label: accountName, key: 'accountName', icon: '🏦' });
        if (accountType) tags.push({ label: accountType, key: 'accountType', icon: '💳' });
        if (categoryId) {
            const cat = categories.find(c => c.id === categoryId);
            tags.push({ label: cat ? cat.name : categoryId, key: 'categoryId', icon: '🏷️' });
        }
        if (dateFrom) tags.push({ label: `From: ${formatDate(dateFrom)}`, key: 'dateFrom', icon: '📅' });
        if (dateTo) tags.push({ label: `To: ${formatDate(dateTo)}`, key: 'dateTo', icon: '📅' });
        return tags;
    };

    const renderStatement = ({ item }: { item: Transaction }) => {
        const isReviewed = item.review_status === 'reviewed';
        const amount = item.Debit
            ? `- ₹${item.Debit.toLocaleString('en-IN')}`
            : item.Credit
                ? `+ ₹${item.Credit.toLocaleString('en-IN')}`
                : '₹0';
        const amountColor = item.Debit ? colors.danger : colors.success;

        return (
            <TouchableOpacity
                style={styles.card}
                onPress={() => navigation.navigate('Details', { id: item.Id })}
            >
                <View style={styles.cardContent}>
                    <View style={styles.cardLeft}>
                        <Text style={styles.cardTitle} numberOfLines={1}>
                            {item.Details || '-'}
                        </Text>
                        <Text style={[styles.cardAmount, { color: amountColor }]}>
                            {amount}
                        </Text>
                        {item.Account_name && (
                            <Text style={styles.cardSubtitle}>
                                {item.Account_name}{item.Account_type ? ` • ${item.Account_type}` : ''}
                            </Text>
                        )}
                    </View>
                    <View style={styles.cardRight}>
                        <View style={[styles.statusBadge, isReviewed ? styles.statusReviewed : styles.statusPending]}>
                            <Text style={[styles.statusText, isReviewed ? styles.statusTextReviewed : styles.statusTextPending]}>
                                {item.review_status}
                            </Text>
                        </View>
                        <Text style={styles.cardDate}>{item.Date || ''}</Text>
                    </View>
                </View>
            </TouchableOpacity>
        );
    };

    const renderFooter = () => {
        if (transactions.length === 0) return null;
        return (
            <View style={styles.footerContainer}>
                <Text style={styles.footerText}>
                    Showing {transactions.length} of {totalCount}
                </Text>
                {loadingMore && <ActivityIndicator size="small" color={colors.primary} style={{ marginTop: spacing.sm }} />}
            </View>
        );
    };

    const filterTags = getFilterTags();

    return (
        <View style={styles.container}>
            <View style={styles.header}>
                {/* Status filter row + Filters toggle */}
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
                    <View style={{ flex: 1 }} />
                    <TouchableOpacity
                        style={[
                            styles.filterToggle,
                            activeFilterCount > 0 && styles.filterToggleActive,
                        ]}
                        onPress={() => showFilters ? setShowFilters(false) : openFilterPanel()}
                    >
                        <Text style={[styles.filterToggleText, activeFilterCount > 0 && styles.filterToggleTextActive]}>
                            ⚙ Filters
                        </Text>
                        {activeFilterCount > 0 && (
                            <View style={styles.filterBadge}>
                                <Text style={styles.filterBadgeText}>{activeFilterCount}</Text>
                            </View>
                        )}
                    </TouchableOpacity>
                </View>

                {/* Active filter tags */}
                {filterTags.length > 0 && (
                    <ScrollView
                        horizontal
                        showsHorizontalScrollIndicator={false}
                        style={styles.tagsRow}
                        contentContainerStyle={styles.tagsContent}
                    >
                        {filterTags.map((tag) => (
                            <TouchableOpacity
                                key={tag.key}
                                style={styles.tag}
                                onPress={() => removeFilter(tag.key)}
                            >
                                <Text style={styles.tagIcon}>{tag.icon}</Text>
                                <Text style={styles.tagLabel}>{tag.label}</Text>
                                <Text style={styles.tagClose}>✕</Text>
                            </TouchableOpacity>
                        ))}
                    </ScrollView>
                )}

                {/* Expandable Advanced Filters Panel */}
                {showFilters && (
                    <View style={styles.advancedFilters}>
                        <View style={styles.pickerWrapper}>
                            <Text style={styles.label}>ACCOUNT</Text>
                            <View style={styles.pickerContainer}>
                                <Picker
                                    selectedValue={pendingAccountName}
                                    onValueChange={(val) => setPendingAccountName(val)}
                                    style={styles.picker}
                                    dropdownIconColor={colors.textSecondary}
                                >
                                    <Picker.Item label="All Accounts" value="" />
                                    {filterOptions.accountNames.map(n => (
                                        <Picker.Item key={n} label={n} value={n} />
                                    ))}
                                </Picker>
                            </View>
                        </View>

                        <View style={styles.pickerWrapper}>
                            <Text style={styles.label}>TYPE</Text>
                            <View style={styles.pickerContainer}>
                                <Picker
                                    selectedValue={pendingAccountType}
                                    onValueChange={(val) => setPendingAccountType(val)}
                                    style={styles.picker}
                                    dropdownIconColor={colors.textSecondary}
                                >
                                    <Picker.Item label="All Types" value="" />
                                    {filterOptions.accountTypes.map(t => (
                                        <Picker.Item key={t} label={t} value={t} />
                                    ))}
                                </Picker>
                            </View>
                        </View>

                        <View style={styles.pickerWrapper}>
                            <Text style={styles.label}>CATEGORY</Text>
                            <View style={styles.pickerContainer}>
                                <Picker
                                    selectedValue={pendingCategoryId}
                                    onValueChange={(val) => setPendingCategoryId(val)}
                                    style={styles.picker}
                                    dropdownIconColor={colors.textSecondary}
                                >
                                    <Picker.Item label="All Categories" value="" />
                                    {categories.map(c => (
                                        <Picker.Item key={c.id} label={c.name} value={c.id} />
                                    ))}
                                </Picker>
                            </View>
                        </View>

                        {/* Date pickers row */}
                        <View style={styles.dateRow}>
                            <View style={styles.dateField}>
                                <Text style={styles.label}>FROM DATE</Text>
                                <TouchableOpacity
                                    style={styles.dateInput}
                                    onPress={() => openDatePicker('from')}
                                >
                                    <Text style={[styles.dateInputText, !pendingDateFrom && styles.dateInputPlaceholder]}>
                                        {pendingDateFrom ? formatDate(pendingDateFrom) : 'Select date'}
                                    </Text>
                                    <Text style={styles.dateInputIcon}>📅</Text>
                                </TouchableOpacity>
                            </View>
                            <View style={styles.dateField}>
                                <Text style={styles.label}>TO DATE</Text>
                                <TouchableOpacity
                                    style={styles.dateInput}
                                    onPress={() => openDatePicker('to')}
                                >
                                    <Text style={[styles.dateInputText, !pendingDateTo && styles.dateInputPlaceholder]}>
                                        {pendingDateTo ? formatDate(pendingDateTo) : 'Select date'}
                                    </Text>
                                    <Text style={styles.dateInputIcon}>📅</Text>
                                </TouchableOpacity>
                            </View>
                        </View>

                        {/* Apply / Clear buttons */}
                        <View style={styles.filterActions}>
                            <TouchableOpacity style={styles.clearButton} onPress={handleClearFilters}>
                                <Text style={styles.clearButtonText}>Clear All</Text>
                            </TouchableOpacity>
                            <TouchableOpacity style={styles.applyButton} onPress={handleApplyFilters}>
                                <Text style={styles.applyButtonText}>Apply</Text>
                            </TouchableOpacity>
                        </View>
                    </View>
                )}
            </View>

            {/* DateTimePicker modal */}
            {showDatePicker && (
                <DateTimePicker
                    value={
                        datePickerTarget === 'from' && pendingDateFrom
                            ? new Date(pendingDateFrom + 'T00:00:00')
                            : datePickerTarget === 'to' && pendingDateTo
                                ? new Date(pendingDateTo + 'T00:00:00')
                                : new Date()
                    }
                    mode="date"
                    display={Platform.OS === 'ios' ? 'spinner' : 'calendar'}
                    onChange={onDateChange}
                    themeVariant="dark"
                />
            )}

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
                    onScroll={(e) => {
                        scrollOffset.current = e.nativeEvent.contentOffset.y;
                    }}
                    onEndReached={handleLoadMore}
                    onEndReachedThreshold={0.3}
                    ListFooterComponent={renderFooter}
                    ListEmptyComponent={
                        <View style={styles.emptyContainer}>
                            <Text style={styles.emptyText}>No transactions found</Text>
                            {(filter || activeFilterCount > 0) && (
                                <TouchableOpacity onPress={() => {
                                    setFilter('');
                                    handleClearFilters();
                                }}>
                                    <Text style={styles.clearFilterText}>Clear Filters</Text>
                                </TouchableOpacity>
                            )}
                        </View>
                    }
                    refreshControl={
                        <RefreshControl
                            refreshing={refreshing}
                            onRefresh={() => {
                                setRefreshing(true);
                                currentSkipRef.current = 0;
                                setTransactions([]);
                                loadStatements(false);
                            }}
                            tintColor={colors.primary}
                        />
                    }
                />
            )}

            {/* Floating Action Button */}
            <TouchableOpacity
                style={styles.fab}
                onPress={() => navigation.navigate('AddExpense')}
            >
                <Text style={styles.fabIcon}>+</Text>
            </TouchableOpacity>
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
    header: {
        paddingBottom: spacing.xs,
        borderBottomWidth: 1,
        borderBottomColor: colors.borderDark,
    },
    filterRow: {
        flexDirection: 'row',
        padding: spacing.md,
        paddingBottom: spacing.sm,
        gap: spacing.sm,
        alignItems: 'center',
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
    // Filter toggle button with badge
    filterToggle: {
        flexDirection: 'row',
        alignItems: 'center',
        paddingHorizontal: spacing.md,
        paddingVertical: spacing.sm,
        borderRadius: borderRadius.full,
        borderWidth: 1,
        borderColor: colors.borderDark,
        backgroundColor: colors.surfaceDark,
        gap: 6,
    },
    filterToggleActive: {
        backgroundColor: colors.primary + '1A', // 10% opacity
        borderColor: colors.primary,
    },
    filterToggleText: {
        color: colors.textSecondary,
        fontSize: 14,
    },
    filterToggleTextActive: {
        color: colors.primary,
        fontWeight: 'bold',
    },
    filterBadge: {
        width: 20,
        height: 20,
        borderRadius: 10,
        backgroundColor: colors.primary,
        justifyContent: 'center',
        alignItems: 'center',
    },
    filterBadgeText: {
        color: colors.white,
        fontSize: 11,
        fontWeight: 'bold',
    },
    // Active filter tags
    tagsRow: {
        maxHeight: 40,
        paddingHorizontal: spacing.md,
        marginBottom: spacing.xs,
    },
    tagsContent: {
        gap: spacing.sm,
        alignItems: 'center',
    },
    tag: {
        flexDirection: 'row',
        alignItems: 'center',
        paddingHorizontal: spacing.sm,
        paddingVertical: 4,
        borderRadius: borderRadius.full,
        backgroundColor: colors.primary + '1A',
        borderWidth: 1,
        borderColor: colors.primary + '4D', // 30%
        gap: 4,
    },
    tagIcon: {
        fontSize: 12,
    },
    tagLabel: {
        color: colors.primary,
        fontSize: 12,
        fontWeight: '600',
    },
    tagClose: {
        color: colors.primary,
        fontSize: 12,
        opacity: 0.6,
        marginLeft: 2,
    },
    // Advanced filter panel
    advancedFilters: {
        paddingHorizontal: spacing.md,
        paddingBottom: spacing.md,
        gap: spacing.sm,
    },
    pickerWrapper: {
        marginBottom: spacing.xs,
    },
    label: {
        color: colors.textSecondary,
        fontSize: 11,
        fontWeight: '600',
        letterSpacing: 0.5,
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
        marginLeft: -8,
    },
    // Date picker inputs
    dateRow: {
        flexDirection: 'row',
        gap: spacing.sm,
    },
    dateField: {
        flex: 1,
    },
    dateInput: {
        flexDirection: 'row',
        alignItems: 'center',
        justifyContent: 'space-between',
        height: 50,
        paddingHorizontal: spacing.md,
        borderRadius: borderRadius.md,
        borderWidth: 1,
        borderColor: colors.borderDark,
        backgroundColor: colors.surfaceDark,
    },
    dateInputText: {
        color: colors.textPrimary,
        fontSize: 14,
    },
    dateInputPlaceholder: {
        color: colors.textSecondary,
    },
    dateInputIcon: {
        fontSize: 16,
    },
    // Apply / Clear buttons
    filterActions: {
        flexDirection: 'row',
        gap: spacing.sm,
        paddingTop: spacing.xs,
    },
    clearButton: {
        flex: 1,
        height: 44,
        borderRadius: borderRadius.md,
        borderWidth: 1,
        borderColor: colors.borderDark,
        justifyContent: 'center',
        alignItems: 'center',
    },
    clearButtonText: {
        color: colors.textSecondary,
        fontSize: 14,
        fontWeight: '600',
    },
    applyButton: {
        flex: 1,
        height: 44,
        borderRadius: borderRadius.md,
        backgroundColor: colors.primary,
        justifyContent: 'center',
        alignItems: 'center',
    },
    applyButtonText: {
        color: colors.white,
        fontWeight: 'bold',
        fontSize: 14,
    },
    // Transaction list
    list: {
        padding: spacing.md,
        paddingTop: spacing.sm,
        paddingBottom: 100,
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
    cardSubtitle: {
        color: colors.textSecondary,
        fontSize: 12,
        marginTop: 2,
    },
    emptyContainer: {
        alignItems: 'center',
        padding: spacing.xl,
    },
    emptyText: {
        color: colors.textSecondary,
        textAlign: 'center',
        marginTop: spacing.xl,
        fontSize: 16,
    },
    clearFilterText: {
        color: colors.primary,
        fontSize: 14,
        fontWeight: 'bold',
        marginTop: spacing.md,
    },
    fab: {
        position: 'absolute',
        right: 20,
        bottom: 20,
        width: 56,
        height: 56,
        borderRadius: 28,
        backgroundColor: colors.primary,
        justifyContent: 'center',
        alignItems: 'center',
        elevation: 8,
        shadowColor: '#000',
        shadowOffset: { width: 0, height: 4 },
        shadowOpacity: 0.3,
        shadowRadius: 4,
    },
    fabIcon: {
        fontSize: 28,
        color: colors.white,
        fontWeight: 'bold',
    },
    footerContainer: {
        paddingVertical: spacing.md,
        alignItems: 'center',
    },
    footerText: {
        color: colors.textSecondary,
        fontSize: 13,
    },
});
