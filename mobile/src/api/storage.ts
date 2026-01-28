import AsyncStorage from '@react-native-async-storage/async-storage';

const API_URL_KEY = '@expense_tracker:api_url';
const LAST_SYNC_KEY = '@expense_tracker:last_sync';
const SYNCED_IDS_KEY = '@expense_tracker:synced_ids';
const DEFAULT_API_URL = 'http://192.168.0.101:8082';

export const storage = {
    /**
     * Get the stored API URL or return the default
     */
    async getApiUrl(): Promise<string> {
        try {
            const url = await AsyncStorage.getItem(API_URL_KEY);
            return url || DEFAULT_API_URL;
        } catch (error) {
            console.error('Error getting API URL:', error);
            return DEFAULT_API_URL;
        }
    },

    /**
     * Save the API URL to storage
     */
    async setApiUrl(url: string): Promise<void> {
        try {
            await AsyncStorage.setItem(API_URL_KEY, url);
        } catch (error) {
            console.error('Error saving API URL:', error);
            throw error;
        }
    },

    /**
     * Reset API URL to default
     */
    async resetApiUrl(): Promise<void> {
        try {
            await AsyncStorage.removeItem(API_URL_KEY);
        } catch (error) {
            console.error('Error resetting API URL:', error);
            throw error;
        }
    },

    /**
     * Get the default API URL
     */
    getDefaultApiUrl(): string {
        return DEFAULT_API_URL;
    },

    /**
     * Get the last sync time
     */
    async getLastSyncTime(): Promise<string | null> {
        try {
            return await AsyncStorage.getItem(LAST_SYNC_KEY);
        } catch (error) {
            console.error('Error getting last sync time:', error);
            return null;
        }
    },

    /**
     * Save the last sync time
     */
    async setLastSyncTime(time: string): Promise<void> {
        try {
            await AsyncStorage.setItem(LAST_SYNC_KEY, time);
        } catch (error) {
            console.error('Error saving last sync time:', error);
            throw error;
        }
    },

    /**
     * Get synced transaction IDs
     */
    async getSyncedTransactionIds(): Promise<string | null> {
        try {
            return await AsyncStorage.getItem(SYNCED_IDS_KEY);
        } catch (error) {
            console.error('Error getting synced IDs:', error);
            return null;
        }
    },

    /**
     * Save synced transaction IDs
     */
    async setSyncedTransactionIds(ids: string): Promise<void> {
        try {
            await AsyncStorage.setItem(SYNCED_IDS_KEY, ids);
        } catch (error) {
            console.error('Error saving synced IDs:', error);
            throw error;
        }
    },
};
