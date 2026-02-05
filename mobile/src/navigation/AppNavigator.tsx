import React from 'react';
import { NavigationContainer } from '@react-navigation/native';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import { Text, View, StyleSheet } from 'react-native';

import HomeScreen from '../screens/HomeScreen';
import UploadScreen from '../screens/UploadScreen';
import FilesScreen from '../screens/FilesScreen';
import TransactionsScreen from '../screens/TransactionsScreen';
import DetailsScreen from '../screens/DetailsScreen';
import AddExpenseScreen from '../screens/AddExpenseScreen';
import SettingsScreen from '../screens/SettingsScreen';
import AccountsScreen from '../screens/AccountsScreen';
import { colors } from '../theme/colors';

// Stack param lists
export type FilesStackParamList = {
    FilesList: undefined;
    Transactions: { filename?: string };
    Details: { id: number };
    AddExpense: undefined;
};

export type HomeStackParamList = {
    HomeMain: undefined;
};

export type AccountsStackParamList = {
    AccountsList: undefined;
};

export type SettingsStackParamList = {
    SettingsMain: undefined;
    Upload: undefined;
};

// Combined type for navigation
export type RootStackParamList = {
    Home: undefined;
    Upload: undefined;
    Files: undefined;
    Transactions: { filename?: string };
    Details: { id: number };
    AddExpense: undefined;
    Settings: undefined;
    Accounts: undefined;
    // Internal Stack Screens
    SettingsMain: undefined;
    FilesList: undefined;
};

const Tab = createBottomTabNavigator();
const FilesStack = createNativeStackNavigator<FilesStackParamList>();
const SettingsStack = createNativeStackNavigator<SettingsStackParamList>();

// Common screen options for stack navigators
const stackScreenOptions = {
    headerStyle: {
        backgroundColor: colors.backgroundDark,
    },
    headerTintColor: colors.textPrimary,
    headerTitleStyle: {
        fontWeight: 'bold' as const,
    },
    contentStyle: {
        backgroundColor: colors.backgroundDark,
    },
};

// Tab icon component
function TabIcon({ name, focused }: { name: string; focused: boolean }) {
    const icons: Record<string, string> = {
        Home: '🏠',
        Files: '📁',
        Accounts: '🏦',
        Settings: '⚙️',
    };
    return (
        <Text style={{ fontSize: 22, opacity: focused ? 1 : 0.5 }}>
            {icons[name] || '📋'}
        </Text>
    );
}

// Files Stack Navigator (Files -> Transactions -> Details)
function FilesStackNavigator() {
    return (
        <FilesStack.Navigator screenOptions={stackScreenOptions}>
            <FilesStack.Screen
                name="FilesList"
                component={FilesScreen}
                options={{ title: 'Files' }}
            />
            <FilesStack.Screen
                name="Transactions"
                component={TransactionsScreen}
                options={{ title: 'Transactions' }}
            />
            <FilesStack.Screen
                name="Details"
                component={DetailsScreen}
                options={{ title: 'Transaction Details' }}
            />
            <FilesStack.Screen
                name="AddExpense"
                component={AddExpenseScreen}
                options={{ title: 'Add Transaction' }}
            />
        </FilesStack.Navigator>
    );
}

// Settings Stack Navigator (Settings -> Upload)
function SettingsStackNavigator() {
    return (
        <SettingsStack.Navigator screenOptions={stackScreenOptions}>
            <SettingsStack.Screen
                name="SettingsMain"
                component={SettingsScreen}
                options={{ title: 'Settings' }}
            />
            <SettingsStack.Screen
                name="Upload"
                component={UploadScreen}
                options={{ title: 'Upload CSV' }}
            />
        </SettingsStack.Navigator>
    );
}

export default function AppNavigator() {
    return (
        <NavigationContainer>
            <Tab.Navigator
                screenOptions={({ route }) => ({
                    tabBarIcon: ({ focused }) => (
                        <TabIcon name={route.name} focused={focused} />
                    ),
                    tabBarActiveTintColor: colors.primary,
                    tabBarInactiveTintColor: colors.textSecondary,
                    tabBarStyle: {
                        backgroundColor: colors.surfaceDark,
                        borderTopColor: colors.borderDark,
                        height: 60,
                        paddingBottom: 8,
                        paddingTop: 8,
                    },
                    tabBarLabelStyle: {
                        fontSize: 11,
                        fontWeight: '600',
                    },
                    headerStyle: {
                        backgroundColor: colors.backgroundDark,
                    },
                    headerTintColor: colors.textPrimary,
                    headerTitleStyle: {
                        fontWeight: 'bold',
                    },
                })}
            >
                <Tab.Screen
                    name="Home"
                    component={HomeScreen}
                    options={{
                        title: 'Home',
                        headerTitle: 'Expense Tracker',
                    }}
                />
                <Tab.Screen
                    name="Files"
                    component={FilesStackNavigator}
                    options={{
                        title: 'Files',
                        headerShown: false,
                    }}
                />
                <Tab.Screen
                    name="Accounts"
                    component={AccountsScreen}
                    options={{
                        title: 'Accounts',
                    }}
                />
                <Tab.Screen
                    name="Settings"
                    component={SettingsStackNavigator}
                    options={{
                        title: 'Settings',
                        headerShown: false,
                    }}
                />
            </Tab.Navigator>
        </NavigationContainer>
    );
}
