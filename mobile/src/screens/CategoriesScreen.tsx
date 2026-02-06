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
import { api, Category } from '../api/client';
import AddCategoryModal from '../components/AddCategoryModal';

type Props = {
    navigation: NativeStackNavigationProp<RootStackParamList, 'Categories'>;
};

export default function CategoriesScreen({ navigation }: Props) {
    const [categories, setCategories] = useState<Category[]>([]);
    const [loading, setLoading] = useState(true);
    const [refreshing, setRefreshing] = useState(false);
    const [modalVisible, setModalVisible] = useState(false);
    const [activeTab, setActiveTab] = useState<'EXPENSE' | 'INCOME'>('EXPENSE');
    const [editingCategory, setEditingCategory] = useState<Category | null>(null);

    const loadCategories = async () => {
        try {
            // Load all categories and filter locally or via API? 
            // API supports filtering: api.getCategories(type)
            const data = await api.getCategories(activeTab);
            setCategories(data);
        } catch (error) {
            console.error('Error loading categories:', error);
            Alert.alert('Error', 'Failed to load categories');
        } finally {
            setLoading(false);
            setRefreshing(false);
        }
    };

    useFocusEffect(
        useCallback(() => {
            loadCategories();
        }, [activeTab])
    );

    const onRefresh = () => {
        setRefreshing(true);
        loadCategories();
    };

    const handleSaveCategory = async (categoryData: {
        id?: string;
        name: string;
        type: 'INCOME' | 'EXPENSE';
    }) => {
        try {
            if (categoryData.id) {
                // Update existing
                const result = await api.updateCategory(categoryData.id, categoryData);
                if (result.success) {
                    await loadCategories(); // Reload to refresh
                } else {
                    Alert.alert('Error', result.error || 'Failed to update category');
                }
            } else {
                // Create new
                const result = await api.createCategory(categoryData);
                if (result.success) {
                    // If added category type matches active tab, reload
                    if (categoryData.type === activeTab) {
                        await loadCategories();
                    } else {
                        Alert.alert('Success', 'Category added');
                    }
                } else {
                    Alert.alert('Error', result.error || 'Failed to create category');
                }
            }
        } catch (error) {
            console.error('Error saving category:', error);
            throw error;
        }
    };

    const handleDeleteCategory = (category: Category) => {
        Alert.alert(
            'Delete Category',
            `Are you sure you want to delete "${category.name}"?`,
            [
                { text: 'Cancel', style: 'cancel' },
                {
                    text: 'Delete',
                    style: 'destructive',
                    onPress: async () => {
                        try {
                            const res = await api.deleteCategory(category.id);
                            if (res.success) {
                                await loadCategories();
                            } else {
                                Alert.alert('Error', res.message || 'Failed to delete');
                            }
                        } catch (error) {
                            console.error('Error deleting category:', error);
                            Alert.alert('Error', 'Failed to delete category');
                        }
                    },
                },
            ]
        );
    };

    const openAddModal = () => {
        setEditingCategory(null);
        setModalVisible(true);
    };

    const openEditModal = (category: Category) => {
        setEditingCategory(category);
        setModalVisible(true);
    };

    const closeModal = () => {
        setModalVisible(false);
        setEditingCategory(null);
    };

    if (loading && !refreshing && categories.length === 0) {
        return (
            <View style={styles.loadingContainer}>
                <ActivityIndicator size="large" color={colors.primary} />
            </View>
        );
    }

    return (
        <View style={styles.container}>
            {/* Header Tabs */}
            <View style={styles.tabContainer}>
                <TouchableOpacity
                    style={[styles.tab, activeTab === 'EXPENSE' && styles.activeTab]}
                    onPress={() => setActiveTab('EXPENSE')}
                >
                    <Text style={[styles.tabText, activeTab === 'EXPENSE' && styles.activeTabText]}>
                        Expense
                    </Text>
                </TouchableOpacity>
                <TouchableOpacity
                    style={[styles.tab, activeTab === 'INCOME' && styles.activeTab]}
                    onPress={() => setActiveTab('INCOME')}
                >
                    <Text style={[styles.tabText, activeTab === 'INCOME' && styles.activeTabText]}>
                        Income
                    </Text>
                </TouchableOpacity>
            </View>

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
                {categories.length === 0 ? (
                    <View style={styles.emptyState}>
                        <Text style={styles.emptyStateIcon}>🏷️</Text>
                        <Text style={styles.emptyStateText}>No categories found</Text>
                        <Text style={styles.emptyStateSubtext}>
                            {activeTab === 'EXPENSE' ? 'Add expense categories' : 'Add income categories'}
                        </Text>
                    </View>
                ) : (
                    <View style={styles.grid}>
                        {categories.map((category) => (
                            <View key={category.id} style={styles.categoryCard}>
                                <View style={styles.categoryInfo}>
                                    <View style={[styles.iconPlaceholder, { backgroundColor: category.color || colors.primary + '20' }]}>
                                        <Text style={styles.iconText}>{category.name.charAt(0).toUpperCase()}</Text>
                                    </View>
                                    <Text style={styles.categoryName} numberOfLines={1}>{category.name}</Text>
                                </View>
                                <View style={styles.actionButtons}>
                                    <TouchableOpacity
                                        style={styles.actionButton}
                                        onPress={() => openEditModal(category)}
                                    >
                                        <Text style={styles.editIcon}>✎</Text>
                                    </TouchableOpacity>
                                    <TouchableOpacity
                                        style={styles.actionButton}
                                        onPress={() => handleDeleteCategory(category)}
                                    >
                                        <Text style={styles.deleteIcon}>×</Text>
                                    </TouchableOpacity>
                                </View>
                            </View>
                        ))}
                    </View>
                )}
            </ScrollView>

            {/* Add Category Button */}
            <TouchableOpacity style={styles.fab} onPress={openAddModal}>
                <Text style={styles.fabIcon}>+</Text>
            </TouchableOpacity>

            {/* Add Category Modal */}
            <AddCategoryModal
                visible={modalVisible}
                onClose={closeModal}
                onSave={handleSaveCategory}
                category={editingCategory}
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
    tabContainer: {
        flexDirection: 'row',
        padding: spacing.md,
        gap: spacing.md,
    },
    tab: {
        flex: 1,
        paddingVertical: spacing.sm,
        alignItems: 'center',
        borderBottomWidth: 2,
        borderBottomColor: 'transparent',
    },
    activeTab: {
        borderBottomColor: colors.primary,
    },
    tabText: {
        color: colors.textSecondary,
        fontSize: 16,
        fontWeight: '600',
    },
    activeTabText: {
        color: colors.primary,
    },
    scrollView: {
        flex: 1,
    },
    scrollContent: {
        padding: spacing.md,
        paddingBottom: 100, // Space for FAB
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
    grid: {
        flexDirection: 'row',
        flexWrap: 'wrap',
        gap: spacing.md,
    },
    categoryCard: {
        width: '47%', // 2 columns with gap
        backgroundColor: colors.surfaceDark,
        borderRadius: borderRadius.lg,
        padding: spacing.md,
        flexDirection: 'row',
        alignItems: 'center',
        justifyContent: 'space-between',
        borderWidth: 1,
        borderColor: colors.borderDark,
    },
    categoryInfo: {
        flexDirection: 'row',
        alignItems: 'center',
        flex: 1,
    },
    iconPlaceholder: {
        width: 32,
        height: 32,
        borderRadius: 16,
        alignItems: 'center',
        justifyContent: 'center',
        marginRight: spacing.sm,
    },
    iconText: {
        color: colors.textPrimary,
        fontWeight: 'bold',
        fontSize: 14,
    },
    categoryName: {
        color: colors.textPrimary,
        fontSize: 14,
        fontWeight: '500',
        flex: 1,
    },
    actionButtons: {
        flexDirection: 'row',
        alignItems: 'center',
    },
    actionButton: {
        padding: spacing.xs,
        marginLeft: spacing.xs,
    },
    editIcon: {
        color: colors.primary,
        fontSize: 18,
        fontWeight: 'bold',
    },
    deleteButton: {
        padding: spacing.xs,
    },
    deleteIcon: {
        color: colors.textSecondary,
        fontSize: 20,
        fontWeight: 'bold',
    },
    fab: {
        position: 'absolute',
        bottom: spacing.lg,
        right: spacing.lg,
        width: 56,
        height: 56,
        borderRadius: 28,
        backgroundColor: colors.primary,
        alignItems: 'center',
        justifyContent: 'center',
        elevation: 6,
        shadowColor: '#000',
        shadowOffset: { width: 0, height: 4 },
        shadowOpacity: 0.3,
        shadowRadius: 4,
    },
    fabIcon: {
        color: colors.white,
        fontSize: 32,
        marginTop: -4,
    },
});
