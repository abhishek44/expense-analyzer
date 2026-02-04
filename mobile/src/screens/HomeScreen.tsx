import React, { useState, useCallback } from 'react';
import {
    View,
    Text,
    StyleSheet,
    TouchableOpacity,
    ScrollView,
    ActivityIndicator,
} from 'react-native';
import { NativeStackNavigationProp } from '@react-navigation/native-stack';
import { useFocusEffect } from '@react-navigation/native';
import { RootStackParamList } from '../navigation/AppNavigator';
import { colors, spacing, borderRadius } from '../theme/colors';
import { api, TableInfo } from '../api/client';

type Props = {
    navigation: NativeStackNavigationProp<RootStackParamList, 'Home'>;
};

export default function HomeScreen({ navigation }: Props) {
    const [stats, setStats] = useState({ pending: 0, reviewed: 0 });
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useFocusEffect(
        useCallback(() => {
            loadStats();
        }, [])
    );

    const loadStats = async () => {
        try {
            setLoading(true);
            setError(null);
            const data = await api.getTables();
            const transactions = data.tables.find(
                (t: TableInfo) => t.name === 'transactions'
            );
            if (transactions) {
                setStats({
                    pending: transactions.pending || 0,
                    reviewed: transactions.reviewed || 0,
                });
            }
        } catch (e) {
            setError('Failed to connect to server');
            console.error(e);
        } finally {
            setLoading(false);
        }
    };

    const menuItems = [
        {
            title: 'Upload CSV',
            subtitle: 'Import bank statement',
            icon: '📤',
            onPress: () => navigation.navigate('Upload'),
        },
        {
            title: 'View Files',
            subtitle: 'Manage uploaded files',
            icon: '📁',
            onPress: () => navigation.navigate('Files'),
        },
        {
            title: 'Add Transaction',
            subtitle: 'Manual entry',
            icon: '➕',
            onPress: () => navigation.navigate('AddExpense'),
        },
        {
            title: 'Accounts',
            subtitle: 'Manage your accounts',
            icon: '🏦',
            onPress: () => navigation.navigate('Accounts'),
        },
    ];

    return (
        <ScrollView style={styles.container}>
            <View style={styles.header}>
                <Text style={styles.title}>Dashboard</Text>
                <TouchableOpacity
                    style={styles.settingsButton}
                    onPress={() => navigation.navigate('Settings')}
                >
                    <Text style={styles.settingsIcon}>⚙️</Text>
                </TouchableOpacity>
            </View>

            {loading ? (
                <ActivityIndicator size="large" color={colors.primary} style={styles.loader} />
            ) : error ? (
                <View style={styles.errorContainer}>
                    <Text style={styles.errorText}>{error}</Text>
                    <TouchableOpacity style={styles.retryButton} onPress={loadStats}>
                        <Text style={styles.retryText}>Retry</Text>
                    </TouchableOpacity>
                </View>
            ) : (
                <View style={styles.statsGrid}>
                    <View style={styles.statCard}>
                        <Text style={styles.statLabel}>Pending</Text>
                        <Text style={[styles.statValue, { color: colors.warning }]}>
                            {stats.pending}
                        </Text>
                    </View>
                    <View style={styles.statCard}>
                        <Text style={styles.statLabel}>Reviewed</Text>
                        <Text style={[styles.statValue, { color: colors.success }]}>
                            {stats.reviewed}
                        </Text>
                    </View>
                </View>
            )}

            <View style={styles.menu}>
                {menuItems.map((item, index) => (
                    <TouchableOpacity
                        key={index}
                        style={styles.menuItem}
                        onPress={item.onPress}
                    >
                        <Text style={styles.menuIcon}>{item.icon}</Text>
                        <View style={styles.menuText}>
                            <Text style={styles.menuTitle}>{item.title}</Text>
                            <Text style={styles.menuSubtitle}>{item.subtitle}</Text>
                        </View>
                        <Text style={styles.chevron}>›</Text>
                    </TouchableOpacity>
                ))}
            </View>
        </ScrollView>
    );
}

const styles = StyleSheet.create({
    container: {
        flex: 1,
        backgroundColor: colors.backgroundDark,
    },
    header: {
        flexDirection: 'row',
        justifyContent: 'space-between',
        alignItems: 'center',
        padding: spacing.md,
    },
    title: {
        fontSize: 24,
        fontWeight: 'bold',
        color: colors.textPrimary,
    },
    settingsButton: {
        padding: spacing.sm,
    },
    settingsIcon: {
        fontSize: 24,
    },
    loader: {
        marginTop: spacing.xl,
    },
    errorContainer: {
        alignItems: 'center',
        padding: spacing.lg,
    },
    errorText: {
        color: colors.danger,
        fontSize: 16,
        marginBottom: spacing.md,
    },
    retryButton: {
        backgroundColor: colors.primary,
        paddingHorizontal: spacing.lg,
        paddingVertical: spacing.sm,
        borderRadius: borderRadius.md,
    },
    retryText: {
        color: colors.white,
        fontWeight: 'bold',
    },
    statsGrid: {
        flexDirection: 'row',
        padding: spacing.md,
        gap: spacing.md,
    },
    statCard: {
        flex: 1,
        backgroundColor: colors.surfaceDark,
        padding: spacing.md,
        borderRadius: borderRadius.lg,
    },
    statLabel: {
        color: colors.textSecondary,
        fontSize: 14,
    },
    statValue: {
        fontSize: 28,
        fontWeight: 'bold',
        marginTop: spacing.xs,
    },
    menu: {
        padding: spacing.md,
        gap: spacing.md,
    },
    menuItem: {
        flexDirection: 'row',
        alignItems: 'center',
        backgroundColor: colors.surfaceDark,
        padding: spacing.md,
        borderRadius: borderRadius.lg,
    },
    menuIcon: {
        fontSize: 24,
        marginRight: spacing.md,
    },
    menuText: {
        flex: 1,
    },
    menuTitle: {
        color: colors.textPrimary,
        fontSize: 16,
        fontWeight: 'bold',
    },
    menuSubtitle: {
        color: colors.textSecondary,
        fontSize: 14,
    },
    chevron: {
        color: colors.textSecondary,
        fontSize: 24,
    },
});
