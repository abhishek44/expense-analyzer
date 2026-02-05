import React, { useState, useEffect } from 'react';
import {
    View,
    Text,
    StyleSheet,
    TouchableOpacity,
    TextInput,
    ScrollView,
    Alert,
    ActivityIndicator,
} from 'react-native';
import { NativeStackNavigationProp } from '@react-navigation/native-stack';
import { RootStackParamList } from '../navigation/AppNavigator';
import { colors, spacing, borderRadius } from '../theme/colors';
import { api } from '../api/client';
import { storage } from '../api/storage';
import { validateUrl } from '../utils/validation';
import { syncService } from '../utils/syncService';

type Props = {
    navigation: NativeStackNavigationProp<RootStackParamList, 'Settings'>;
};

export default function SettingsScreen({ navigation }: Props) {
    const [backendUrl, setBackendUrl] = useState('');
    const [currentUrl, setCurrentUrl] = useState('');
    const [syncing, setSyncing] = useState(false);
    const [lastSyncTime, setLastSyncTime] = useState<string | null>(null);

    useEffect(() => {
        loadSettings();
    }, []);

    const loadSettings = async () => {
        const url = await storage.getApiUrl();
        setCurrentUrl(url);
        setBackendUrl(url);

        const lastSync = await storage.getLastSyncTime();
        setLastSyncTime(lastSync);
    };

    const handleSaveBackendUrl = async () => {
        if (!backendUrl.trim()) {
            Alert.alert('Error', 'Please enter a backend URL');
            return;
        }

        if (!validateUrl(backendUrl)) {
            Alert.alert('Error', 'Please enter a valid URL (e.g., http://192.168.0.101:8082)');
            return;
        }

        try {
            await storage.setApiUrl(backendUrl);
            syncService.setBackendUrl(backendUrl);
            setCurrentUrl(backendUrl);
            Alert.alert('Success', 'Backend URL updated successfully!');
        } catch (e) {
            Alert.alert('Error', 'Failed to save backend URL');
        }
    };

    const handleResetUrl = async () => {
        const defaultUrl = storage.getDefaultApiUrl();
        setBackendUrl(defaultUrl);
        await storage.resetApiUrl();
        syncService.setBackendUrl(defaultUrl);
        setCurrentUrl(defaultUrl);
        Alert.alert('Success', 'Reset to default URL');
    };

    const handleSync = async () => {
        if (!currentUrl) {
            Alert.alert('Error', 'Please configure backend URL first');
            return;
        }

        setSyncing(true);
        try {
            const result = await syncService.sync();

            if (result.success) {
                const syncTime = new Date().toISOString();
                await storage.setLastSyncTime(syncTime);
                setLastSyncTime(syncTime);

                Alert.alert(
                    'Sync Complete',
                    `✅ Uploaded: ${result.uploaded} transactions\n✅ Downloaded: ${result.downloaded} transactions`,
                    [{ text: 'OK' }]
                );
            } else {
                Alert.alert(
                    'Sync Completed with Errors',
                    `Uploaded: ${result.uploaded}\nDownloaded: ${result.downloaded}\n\nErrors:\n${result.errors.join('\n')}`,
                    [{ text: 'OK' }]
                );
            }
        } catch (error: any) {
            Alert.alert('Sync Failed', error.message || 'Unknown error occurred');
        } finally {
            setSyncing(false);
        }
    };

    const handleClearTransactions = () => {
        Alert.alert(
            'Clear All Transactions',
            'Delete ALL transaction records? This cannot be undone.',
            [
                { text: 'Cancel', style: 'cancel' },
                {
                    text: 'Delete',
                    style: 'destructive',
                    onPress: async () => {
                        try {
                            const result = await api.clearTable('transactions');
                            Alert.alert('Success', result.message);
                        } catch (e) {
                            Alert.alert('Error', 'Failed to clear transactions');
                        }
                    },
                },
            ]
        );
    };

    const formatSyncTime = (isoString: string | null): string => {
        if (!isoString) return 'Never';
        const date = new Date(isoString);
        return date.toLocaleString();
    };

    return (
        <ScrollView style={styles.container} contentContainerStyle={styles.content}>
            {/* Backend Configuration */}
            <View style={styles.card}>
                <Text style={styles.cardTitle}>Backend Sync (Optional)</Text>
                <Text style={styles.description}>
                    Configure backend URL to sync data between devices. App works offline without this.
                </Text>

                <Text style={styles.currentUrlLabel}>Current URL:</Text>
                <Text style={styles.currentUrlValue}>{currentUrl}</Text>

                <View style={styles.urlInputRow}>
                    <TextInput
                        style={styles.urlInput}
                        value={backendUrl}
                        onChangeText={setBackendUrl}
                        placeholder="http://192.168.0.101:8082"
                        placeholderTextColor={colors.textSecondary}
                        autoCapitalize="none"
                        autoCorrect={false}
                    />
                </View>

                <View style={styles.urlButtonRow}>
                    <TouchableOpacity
                        style={styles.saveUrlButton}
                        onPress={handleSaveBackendUrl}
                    >
                        <Text style={styles.saveUrlText}>Save URL</Text>
                    </TouchableOpacity>
                    <TouchableOpacity
                        style={styles.resetUrlButton}
                        onPress={handleResetUrl}
                    >
                        <Text style={styles.resetUrlText}>Reset</Text>
                    </TouchableOpacity>
                </View>
            </View>

            {/* Sync Section */}
            <View style={styles.card}>
                <Text style={styles.cardTitle}>Synchronization</Text>
                <Text style={styles.syncInfo}>
                    Last sync: {formatSyncTime(lastSyncTime)}
                </Text>

                <TouchableOpacity
                    style={[styles.syncButton, syncing && styles.syncButtonDisabled]}
                    onPress={handleSync}
                    disabled={syncing}
                >
                    {syncing ? (
                        <>
                            <ActivityIndicator size="small" color={colors.white} />
                            <Text style={styles.syncButtonText}>Syncing...</Text>
                        </>
                    ) : (
                        <>
                            <Text style={styles.syncIcon}>🔄</Text>
                            <Text style={styles.syncButtonText}>Sync Now</Text>
                        </>
                    )}
                </TouchableOpacity>

                <Text style={styles.syncDescription}>
                    Uploads local transactions to backend and downloads new transactions from backend.
                </Text>
            </View>

            {/* Data Management */}
            <View style={styles.card}>
                <Text style={styles.cardTitle}>Data Management</Text>

                <TouchableOpacity
                    style={styles.dataButton}
                    onPress={() => navigation.navigate('Upload')}
                >
                    <Text style={styles.dataButtonIcon}>📤</Text>
                    <View style={styles.dataButtonContent}>
                        <Text style={styles.dataButtonTitle}>Upload CSV</Text>
                        <Text style={styles.dataButtonSubtitle}>Import bank statement</Text>
                    </View>
                </TouchableOpacity>
            </View>

            {/* Danger Zone */}
            <View style={styles.card}>
                <Text style={styles.dangerTitle}>Danger Zone</Text>
                <TouchableOpacity
                    style={styles.dangerButton}
                    onPress={handleClearTransactions}
                >
                    <Text style={styles.dangerButtonText}>Clear All Transactions</Text>
                </TouchableOpacity>
            </View>

            {/* About */}
            <View style={styles.card}>
                <Text style={styles.cardTitle}>About</Text>
                <Text style={styles.aboutText}>Expense Tracker v1.0.0 (Offline-First)</Text>
                <Text style={styles.aboutSubtext}>
                    Built with React Native + Expo{'\n'}Works completely offline with optional cloud sync
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
    content: {
        padding: spacing.md,
    },
    card: {
        backgroundColor: colors.surfaceDark,
        borderRadius: borderRadius.lg,
        padding: spacing.md,
        marginBottom: spacing.md,
    },
    cardTitle: {
        color: colors.textPrimary,
        fontSize: 16,
        fontWeight: 'bold',
        marginBottom: spacing.md,
    },
    description: {
        color: colors.textSecondary,
        fontSize: 12,
        marginBottom: spacing.md,
        lineHeight: 18,
    },
    currentUrlLabel: {
        color: colors.textSecondary,
        fontSize: 12,
        marginBottom: spacing.xs,
    },
    currentUrlValue: {
        color: colors.textPrimary,
        fontSize: 14,
        fontFamily: 'monospace',
        marginBottom: spacing.md,
        padding: spacing.sm,
        backgroundColor: colors.backgroundDark,
        borderRadius: borderRadius.sm,
    },
    urlInputRow: {
        marginBottom: spacing.md,
    },
    urlInput: {
        backgroundColor: colors.backgroundDark,
        borderWidth: 1,
        borderColor: colors.borderDark,
        borderRadius: borderRadius.md,
        padding: spacing.md,
        color: colors.textPrimary,
        fontSize: 14,
        fontFamily: 'monospace',
    },
    urlButtonRow: {
        flexDirection: 'row',
        gap: spacing.sm,
    },
    saveUrlButton: {
        flex: 1,
        backgroundColor: colors.primary,
        borderRadius: borderRadius.md,
        padding: spacing.sm,
        alignItems: 'center',
    },
    saveUrlText: {
        color: colors.white,
        fontWeight: 'bold',
        fontSize: 14,
    },
    resetUrlButton: {
        flex: 1,
        backgroundColor: colors.backgroundDark,
        borderWidth: 1,
        borderColor: colors.borderDark,
        borderRadius: borderRadius.md,
        padding: spacing.sm,
        alignItems: 'center',
    },
    resetUrlText: {
        color: colors.textSecondary,
        fontWeight: 'bold',
        fontSize: 14,
    },
    syncInfo: {
        color: colors.textSecondary,
        fontSize: 12,
        marginBottom: spacing.md,
    },
    syncButton: {
        backgroundColor: colors.success,
        borderRadius: borderRadius.md,
        padding: spacing.md,
        flexDirection: 'row',
        justifyContent: 'center',
        alignItems: 'center',
        gap: spacing.sm,
        marginBottom: spacing.sm,
    },
    syncButtonDisabled: {
        backgroundColor: colors.success + '80',
    },
    syncIcon: {
        fontSize: 18,
    },
    syncButtonText: {
        color: colors.white,
        fontWeight: 'bold',
        fontSize: 16,
    },
    syncDescription: {
        color: colors.textSecondary,
        fontSize: 11,
        lineHeight: 16,
    },
    dangerTitle: {
        color: colors.danger,
        fontSize: 16,
        fontWeight: 'bold',
        marginBottom: spacing.md,
    },
    dangerButton: {
        backgroundColor: colors.danger + '20',
        borderRadius: borderRadius.md,
        padding: spacing.sm,
        alignItems: 'center',
        marginBottom: spacing.sm,
    },
    dangerButtonText: {
        color: colors.danger,
        fontWeight: 'bold',
        fontSize: 14,
    },
    aboutText: {
        color: colors.textPrimary,
        fontSize: 14,
    },
    aboutSubtext: {
        color: colors.textSecondary,
        fontSize: 12,
        marginTop: spacing.xs,
    },
    dataButton: {
        flexDirection: 'row',
        alignItems: 'center',
        backgroundColor: colors.backgroundDark,
        borderRadius: borderRadius.md,
        padding: spacing.md,
        marginBottom: spacing.sm,
    },
    dataButtonIcon: {
        fontSize: 24,
        marginRight: spacing.md,
    },
    dataButtonContent: {
        flex: 1,
    },
    dataButtonTitle: {
        color: colors.textPrimary,
        fontSize: 14,
        fontWeight: 'bold',
    },
    dataButtonSubtitle: {
        color: colors.textSecondary,
        fontSize: 12,
        marginTop: 2,
    },
});
