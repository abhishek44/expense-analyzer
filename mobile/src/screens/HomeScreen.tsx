import React, { useState, useCallback } from 'react';
import {
    View,
    Text,
    StyleSheet,
    TouchableOpacity,
    ScrollView,
    ActivityIndicator,
} from 'react-native';
import { useFocusEffect } from '@react-navigation/native';
import { colors, spacing, borderRadius } from '../theme/colors';
import { api, TableInfo } from '../api/client';

export default function HomeScreen() {
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
            setError('Failed to load data');
            console.error(e);
        } finally {
            setLoading(false);
        }
    };

    return (
        <ScrollView style={styles.container}>
            <View style={styles.header}>
                <Text style={styles.title}>Dashboard</Text>
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

            <View style={styles.infoCard}>
                <Text style={styles.infoTitle}>Welcome to Expense Tracker</Text>
                <Text style={styles.infoText}>
                    Use the bottom tabs to navigate:{'\n'}
                    • Files: View and manage uploaded files{'\n'}
                    • Accounts: Manage your financial accounts{'\n'}
                    • Settings: Configure app settings and upload CSVs
                </Text>
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
        padding: spacing.md,
    },
    title: {
        fontSize: 24,
        fontWeight: 'bold',
        color: colors.textPrimary,
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
    infoCard: {
        margin: spacing.md,
        backgroundColor: colors.surfaceDark,
        padding: spacing.md,
        borderRadius: borderRadius.lg,
    },
    infoTitle: {
        color: colors.textPrimary,
        fontSize: 16,
        fontWeight: 'bold',
        marginBottom: spacing.sm,
    },
    infoText: {
        color: colors.textSecondary,
        fontSize: 14,
        lineHeight: 22,
    },
});
