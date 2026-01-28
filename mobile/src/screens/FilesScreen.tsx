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
} from 'react-native';
import { NativeStackNavigationProp } from '@react-navigation/native-stack';
import { useFocusEffect } from '@react-navigation/native';
import { RootStackParamList } from '../navigation/AppNavigator';
import { colors, spacing, borderRadius } from '../theme/colors';
import { api, UploadedFile } from '../api/client';

type Props = {
    navigation: NativeStackNavigationProp<RootStackParamList, 'Files'>;
};

export default function FilesScreen({ navigation }: Props) {
    const [files, setFiles] = useState<UploadedFile[]>([]);
    const [loading, setLoading] = useState(true);
    const [refreshing, setRefreshing] = useState(false);

    useFocusEffect(
        useCallback(() => {
            loadFiles();
        }, [])
    );

    const loadFiles = async () => {
        try {
            setLoading(true);
            const data = await api.getUploadedFiles();
            setFiles(data.files);
        } catch (e) {
            Alert.alert('Error', 'Failed to load files');
            console.error(e);
        } finally {
            setLoading(false);
            setRefreshing(false);
        }
    };

    const handleDelete = (filename: string) => {
        Alert.alert(
            'Delete File',
            `Delete all records for "${filename}"?`,
            [
                { text: 'Cancel', style: 'cancel' },
                {
                    text: 'Delete',
                    style: 'destructive',
                    onPress: async () => {
                        try {
                            const result = await api.deleteFile(filename);
                            if (result.success) {
                                Alert.alert('Success', result.message);
                                loadFiles();
                            }
                        } catch (e) {
                            Alert.alert('Error', 'Failed to delete file');
                        }
                    },
                },
            ]
        );
    };

    const renderFile = ({ item }: { item: UploadedFile }) => (
        <View style={styles.fileCard}>
            <View style={styles.fileHeader}>
                <View style={styles.fileInfo}>
                    <Text style={styles.fileName} numberOfLines={1}>
                        {item.filename}
                    </Text>
                    <Text style={styles.fileMeta}>
                        {item.account_type || 'N/A'} • {item.account_name || 'N/A'}
                    </Text>
                </View>
                <TouchableOpacity
                    style={styles.deleteButton}
                    onPress={() => handleDelete(item.filename)}
                >
                    <Text style={styles.deleteIcon}>🗑️</Text>
                </TouchableOpacity>
            </View>

            <View style={styles.statsRow}>
                <Text style={styles.statPending}>{item.pending_count} pending</Text>
                <Text style={styles.statReviewed}>{item.reviewed_count} reviewed</Text>
            </View>

            <TouchableOpacity
                style={styles.viewButton}
                onPress={() => navigation.navigate('Transactions', { filename: item.filename })}
            >
                <Text style={styles.viewButtonText}>View Transactions</Text>
            </TouchableOpacity>
        </View>
    );

    if (loading && !refreshing) {
        return (
            <View style={styles.centered}>
                <ActivityIndicator size="large" color={colors.primary} />
            </View>
        );
    }

    return (
        <View style={styles.container}>
            <FlatList
                data={files}
                renderItem={renderFile}
                keyExtractor={(item) => item.filename}
                contentContainerStyle={styles.list}
                ListEmptyComponent={
                    <Text style={styles.emptyText}>No files uploaded yet</Text>
                }
                refreshControl={
                    <RefreshControl
                        refreshing={refreshing}
                        onRefresh={() => {
                            setRefreshing(true);
                            loadFiles();
                        }}
                        tintColor={colors.primary}
                    />
                }
            />
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
        backgroundColor: colors.backgroundDark,
    },
    list: {
        padding: spacing.md,
        gap: spacing.md,
    },
    fileCard: {
        backgroundColor: colors.surfaceDark,
        borderRadius: borderRadius.lg,
        padding: spacing.md,
        marginBottom: spacing.md,
    },
    fileHeader: {
        flexDirection: 'row',
        justifyContent: 'space-between',
        alignItems: 'flex-start',
        marginBottom: spacing.sm,
    },
    fileInfo: {
        flex: 1,
        marginRight: spacing.sm,
    },
    fileName: {
        color: colors.textPrimary,
        fontSize: 16,
        fontWeight: 'bold',
    },
    fileMeta: {
        color: colors.textSecondary,
        fontSize: 14,
        marginTop: spacing.xs,
    },
    deleteButton: {
        padding: spacing.sm,
    },
    deleteIcon: {
        fontSize: 20,
    },
    statsRow: {
        flexDirection: 'row',
        gap: spacing.md,
        marginBottom: spacing.md,
    },
    statPending: {
        color: colors.warning,
        fontSize: 14,
    },
    statReviewed: {
        color: colors.success,
        fontSize: 14,
    },
    viewButton: {
        backgroundColor: colors.primary,
        borderRadius: borderRadius.md,
        padding: spacing.sm,
        alignItems: 'center',
    },
    viewButtonText: {
        color: colors.white,
        fontWeight: 'bold',
        fontSize: 14,
    },
    emptyText: {
        color: colors.textSecondary,
        textAlign: 'center',
        marginTop: spacing.xl,
        fontSize: 16,
    },
});
