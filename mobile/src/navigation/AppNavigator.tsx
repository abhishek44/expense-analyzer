import React from 'react';
import { NavigationContainer } from '@react-navigation/native';
import { createNativeStackNavigator } from '@react-navigation/native-stack';

import HomeScreen from '../screens/HomeScreen';
import UploadScreen from '../screens/UploadScreen';
import FilesScreen from '../screens/FilesScreen';
import TransactionsScreen from '../screens/TransactionsScreen';
import DetailsScreen from '../screens/DetailsScreen';
import AddExpenseScreen from '../screens/AddExpenseScreen';
import SettingsScreen from '../screens/SettingsScreen';
import { colors } from '../theme/colors';

export type RootStackParamList = {
    Home: undefined;
    Upload: undefined;
    Files: undefined;
    Transactions: { filename?: string };
    Details: { id: number };
    AddExpense: undefined;
    Settings: undefined;
};

const Stack = createNativeStackNavigator<RootStackParamList>();

export default function AppNavigator() {
    return (
        <NavigationContainer>
            <Stack.Navigator
                initialRouteName="Home"
                screenOptions={{
                    headerStyle: {
                        backgroundColor: colors.backgroundDark,
                    },
                    headerTintColor: colors.textPrimary,
                    headerTitleStyle: {
                        fontWeight: 'bold',
                    },
                    contentStyle: {
                        backgroundColor: colors.backgroundDark,
                    },
                }}
            >
                <Stack.Screen
                    name="Home"
                    component={HomeScreen}
                    options={{ title: 'Expense Tracker' }}
                />
                <Stack.Screen
                    name="Upload"
                    component={UploadScreen}
                    options={{ title: 'Upload CSV' }}
                />
                <Stack.Screen
                    name="Files"
                    component={FilesScreen}
                    options={{ title: 'Uploaded Files' }}
                />
                <Stack.Screen
                    name="Transactions"
                    component={TransactionsScreen}
                    options={{ title: 'Transactions' }}
                />
                <Stack.Screen
                    name="Details"
                    component={DetailsScreen}
                    options={{ title: 'Transaction Details' }}
                />
                <Stack.Screen
                    name="AddExpense"
                    component={AddExpenseScreen}
                    options={{ title: 'Add Expense' }}
                />
                <Stack.Screen
                    name="Settings"
                    component={SettingsScreen}
                    options={{ title: 'Settings' }}
                />
            </Stack.Navigator>
        </NavigationContainer>
    );
}
