import React, { useState } from 'react';
import {
    View,
    Text,
    StyleSheet,
    TouchableOpacity,
    TextInput,
    ActivityIndicator,
    Alert,
} from 'react-native';
import * as DocumentPicker from 'expo-document-picker';
import { NativeStackNavigationProp } from '@react-navigation/native-stack';
import { RootStackParamList } from '../navigation/AppNavigator';
import { colors, spacing, borderRadius } from '../theme/colors';
import { api } from '../api/client';

type Props = {
    navigation: NativeStackNavigationProp<RootStackParamList, 'Upload'>;
};

const accountTypes = ['Credit Card', 'Savings', 'Current'];

export default function UploadScreen({ navigation }: Props) {
    const [accountType, setAccountType] = useState('Credit Card');
    const [accountName, setAccountName] = useState('');
    const [uploading, setUploading] = useState(false);
    const [selectedFile, setSelectedFile] = useState<string | null>(null);

    const pickDocument = async () => {
        try {
            // Use */* to allow selection on all Android devices/versions
            // Some devices don't correctly register text/csv
            const result = await DocumentPicker.getDocumentAsync({
                type: '*/*',
                copyToCacheDirectory: true,
            });

            if (!result.canceled && result.assets && result.assets.length > 0) {
                const file = result.assets[0];

                // Validate extension
                if (!file.name.toLowerCase().endsWith('.csv')) {
                    Alert.alert('Invalid File', 'Please select a CSV file (.csv)');
                    return;
                }

                setSelectedFile(file.name);
                await uploadFile(file.uri, file.name);
            }
        } catch (err) {
            Alert.alert('Error', 'Failed to pick document');
            console.error(err);
        }
    };

    const uploadFile = async (uri: string, fileName: string, force: boolean = false) => {
        setUploading(true);
        try {
            // Combine account type and name for the account_name field
            const fullAccountName = accountName
                ? `${accountType} - ${accountName}`
                : accountType;

            const result = await api.uploadCSV(uri, fileName, fullAccountName, force);

            if (result.success) {
                Alert.alert(
                    'Success',
                    `Uploaded ${result.rows_inserted} rows successfully!`,
                    [{ text: 'OK', onPress: () => navigation.navigate('Files') }]
                );
            } else if (result.isDuplicate && result.duplicateInfo) {
                // Handle duplicate detection
                const { uploadDate, transactionCount } = result.duplicateInfo;
                const dateStr = new Date(uploadDate).toLocaleString();

                Alert.alert(
                    'Duplicate File Detected',
                    `This file (same name & content) was already uploaded on ${dateStr} with ${transactionCount} transactions.\n\nDo you want to upload it again?`,
                    [
                        {
                            text: 'Cancel',
                            style: 'cancel',
                            onPress: () => {
                                setUploading(false);
                                setSelectedFile(null);
                            }
                        },
                        {
                            text: 'Upload Anyway',
                            style: 'destructive',
                            onPress: () => uploadFile(uri, fileName, true)
                        }
                    ]
                );
                // Don't clear uploading state yet if we might retry
                return;
            } else {
                Alert.alert('Error', result.message || 'Upload failed');
            }
        } catch (err) {
            Alert.alert('Error', 'Failed to upload file. Please try again.');
            console.error(err);
        } finally {
            setUploading(false);
            setSelectedFile(null);
        }
    };

    return (
        <View style={styles.container}>
            <View style={styles.form}>
                <View style={styles.field}>
                    <Text style={styles.label}>Account Type</Text>
                    <View style={styles.pickerContainer}>
                        {accountTypes.map((type) => (
                            <TouchableOpacity
                                key={type}
                                style={[
                                    styles.pickerOption,
                                    accountType === type && styles.pickerOptionSelected,
                                ]}
                                onPress={() => setAccountType(type)}
                            >
                                <Text
                                    style={[
                                        styles.pickerText,
                                        accountType === type && styles.pickerTextSelected,
                                    ]}
                                >
                                    {type}
                                </Text>
                            </TouchableOpacity>
                        ))}
                    </View>
                </View>

                <View style={styles.field}>
                    <Text style={styles.label}>Account Name/Number</Text>
                    <TextInput
                        style={styles.input}
                        placeholder="e.g. HDFC 1234"
                        placeholderTextColor={colors.textSecondary}
                        value={accountName}
                        onChangeText={setAccountName}
                    />
                </View>
            </View>

            {uploading ? (
                <View style={styles.uploadingContainer}>
                    <ActivityIndicator size="large" color={colors.primary} />
                    <Text style={styles.uploadingText}>Uploading {selectedFile}...</Text>
                </View>
            ) : (
                <TouchableOpacity style={styles.dropZone} onPress={pickDocument}>
                    <Text style={styles.dropIcon}>☁️</Text>
                    <Text style={styles.dropTitle}>Upload CSV File</Text>
                    <Text style={styles.dropSubtitle}>Tap to browse files (works offline)</Text>
                </TouchableOpacity>
            )}
        </View>
    );
}

const styles = StyleSheet.create({
    container: {
        flex: 1,
        backgroundColor: colors.backgroundDark,
        padding: spacing.md,
    },
    form: {
        gap: spacing.md,
        marginBottom: spacing.lg,
    },
    field: {
        gap: spacing.sm,
    },
    label: {
        color: colors.textPrimary,
        fontSize: 14,
        fontWeight: '500',
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
    pickerContainer: {
        flexDirection: 'row',
        gap: spacing.sm,
    },
    pickerOption: {
        flex: 1,
        backgroundColor: colors.surfaceDark,
        borderWidth: 1,
        borderColor: colors.borderDark,
        borderRadius: borderRadius.md,
        padding: spacing.sm,
        alignItems: 'center',
    },
    pickerOptionSelected: {
        borderColor: colors.primary,
        backgroundColor: colors.primary + '20',
    },
    pickerText: {
        color: colors.textSecondary,
        fontSize: 12,
    },
    pickerTextSelected: {
        color: colors.primary,
        fontWeight: 'bold',
    },
    dropZone: {
        flex: 1,
        borderWidth: 2,
        borderColor: colors.borderDark,
        borderStyle: 'dashed',
        borderRadius: borderRadius.lg,
        justifyContent: 'center',
        alignItems: 'center',
        gap: spacing.sm,
    },
    dropIcon: {
        fontSize: 48,
    },
    dropTitle: {
        color: colors.textPrimary,
        fontSize: 18,
        fontWeight: 'bold',
    },
    dropSubtitle: {
        color: colors.textSecondary,
        fontSize: 14,
    },
    uploadingContainer: {
        flex: 1,
        justifyContent: 'center',
        alignItems: 'center',
        gap: spacing.md,
    },
    uploadingText: {
        color: colors.textSecondary,
        fontSize: 16,
    },
});
