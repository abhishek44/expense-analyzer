import { database, Transaction, Category, Account } from '../database/database';
import { storage } from '../api/storage';
import base64 from 'react-native-base64';

export interface SyncResult {
    success: boolean;
    transactions: { uploaded: number; downloaded: number };
    categories: { uploaded: number; downloaded: number };
    accounts: { uploaded: number; downloaded: number };
    errors: string[];
}

// Legacy interface for backward compatibility
export interface LegacySyncResult {
    success: boolean;
    uploaded: number;
    downloaded: number;
    errors: string[];
}

/**
 * Sync service for bidirectional sync with FastAPI backend
 * Syncs: Categories, Accounts, Transactions (in that order due to dependencies)
 */
class SyncService {
    private baseUrl: string = '';
    private lastSyncedIds: Set<number> = new Set();
    private lastSyncedCategoryIds: Set<string> = new Set();
    private lastSyncedAccountIds: Set<string> = new Set();

    /**
     * Initialize sync service with backend URL
     */
    async init(): Promise<void> {
        this.baseUrl = await storage.getApiUrl();
        await this.loadSyncedIds();
    }

    /**
     * Load previously synced IDs from database
     */
    private async loadSyncedIds(): Promise<void> {
        try {
            // Load transaction synced IDs
            const syncedIds = await database.getSyncedTransactionIds();
            this.lastSyncedIds = new Set(syncedIds);
            console.log(`Loaded ${this.lastSyncedIds.size} synced transaction IDs from DB`);

            // Load category synced IDs
            const syncedCategoryIds = await database.getSyncedCategoryIds();
            this.lastSyncedCategoryIds = new Set(syncedCategoryIds);
            console.log(`Loaded ${this.lastSyncedCategoryIds.size} synced category IDs from DB`);

            // Load account synced IDs
            const syncedAccountIds = await database.getSyncedAccountIds();
            this.lastSyncedAccountIds = new Set(syncedAccountIds);
            console.log(`Loaded ${this.lastSyncedAccountIds.size} synced account IDs from DB`);
        } catch (error) {
            console.error('Failed to load synced IDs:', error);
            this.lastSyncedIds = new Set();
            this.lastSyncedCategoryIds = new Set();
            this.lastSyncedAccountIds = new Set();
        }
    }

    /**
     * Update backend URL
     */
    setBackendUrl(url: string): void {
        this.baseUrl = url;
    }

    /**
     * Check if backend is reachable
     */
    async checkConnection(): Promise<boolean> {
        try {
            const response = await fetch(`${this.baseUrl}/health`, {
                method: 'GET',
                headers: { 'Content-Type': 'application/json' },
            });
            return response.ok;
        } catch {
            return false;
        }
    }

    // ==================== CATEGORY SYNC ====================

    /**
     * Upload local categories to backend
     */
    private async uploadCategoriesToBackend(): Promise<{ count: number; errors: string[] }> {
        const errors: string[] = [];
        let uploadedCount = 0;

        try {
            const localCategories = await database.exportAllCategories();

            if (localCategories.length === 0) {
                return { count: 0, errors: [] };
            }

            // Filter out categories that have already been synced
            const newCategories = localCategories.filter(
                c => !this.lastSyncedCategoryIds.has(c.id)
            );

            if (newCategories.length === 0) {
                console.log('No new categories to upload');
                return { count: 0, errors: [] };
            }

            console.log(`Uploading ${newCategories.length} categories...`);

            const response = await fetch(`${this.baseUrl}/api/categories/batch`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(newCategories),
            });

            if (response.ok) {
                uploadedCount = newCategories.length;
                const syncedIds = newCategories.map(c => c.id);
                await database.markCategoriesAsSynced(syncedIds);
                syncedIds.forEach(id => this.lastSyncedCategoryIds.add(id));
            } else {
                const errorText = await response.text().catch(() => 'Unknown error');
                errors.push(`Failed to upload categories: ${errorText}`);
            }
        } catch (error: any) {
            errors.push(`Category upload error: ${error.message}`);
        }

        return { count: uploadedCount, errors };
    }

    /**
     * Download categories from backend
     */
    private async downloadCategoriesFromBackend(): Promise<{ count: number; errors: string[] }> {
        const errors: string[] = [];
        let downloadedCount = 0;

        try {
            const response = await fetch(`${this.baseUrl}/api/categories?include_archived=true`, {
                method: 'GET',
                headers: { 'Content-Type': 'application/json' },
            });

            if (!response.ok) {
                throw new Error('Failed to fetch categories from backend');
            }

            const backendCategories: Category[] = await response.json();

            if (backendCategories.length === 0) {
                return { count: 0, errors: [] };
            }

            console.log(`Received ${backendCategories.length} categories from backend`);

            // Upsert each category (handles insert or update based on updated_at)
            for (const cat of backendCategories) {
                await database.upsertCategory(cat);
                downloadedCount++;
            }

            // Mark all as synced
            const syncedIds = backendCategories.map(c => c.id);
            await database.markCategoriesAsSynced(syncedIds);
            syncedIds.forEach(id => this.lastSyncedCategoryIds.add(id));

        } catch (error: any) {
            errors.push(`Category download error: ${error.message}`);
        }

        return { count: downloadedCount, errors };
    }

    // ==================== ACCOUNT SYNC ====================

    /**
     * Upload local accounts to backend
     */
    private async uploadAccountsToBackend(): Promise<{ count: number; errors: string[] }> {
        const errors: string[] = [];
        let uploadedCount = 0;

        try {
            const localAccounts = await database.exportAllAccounts();

            if (localAccounts.length === 0) {
                return { count: 0, errors: [] };
            }

            // Filter out accounts that have already been synced
            const newAccounts = localAccounts.filter(
                a => !this.lastSyncedAccountIds.has(a.id)
            );

            if (newAccounts.length === 0) {
                console.log('No new accounts to upload');
                return { count: 0, errors: [] };
            }

            console.log(`Uploading ${newAccounts.length} accounts...`);

            const response = await fetch(`${this.baseUrl}/api/accounts/batch`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(newAccounts),
            });

            if (response.ok) {
                uploadedCount = newAccounts.length;
                const syncedIds = newAccounts.map(a => a.id);
                await database.markAccountsAsSynced(syncedIds);
                syncedIds.forEach(id => this.lastSyncedAccountIds.add(id));
            } else {
                const errorText = await response.text().catch(() => 'Unknown error');
                errors.push(`Failed to upload accounts: ${errorText}`);
            }
        } catch (error: any) {
            errors.push(`Account upload error: ${error.message}`);
        }

        return { count: uploadedCount, errors };
    }

    /**
     * Download accounts from backend
     */
    private async downloadAccountsFromBackend(): Promise<{ count: number; errors: string[] }> {
        const errors: string[] = [];
        let downloadedCount = 0;

        try {
            const response = await fetch(`${this.baseUrl}/api/accounts?include_archived=true`, {
                method: 'GET',
                headers: { 'Content-Type': 'application/json' },
            });

            if (!response.ok) {
                throw new Error('Failed to fetch accounts from backend');
            }

            const result = await response.json();
            const backendAccounts: Account[] = result.accounts || [];

            if (backendAccounts.length === 0) {
                return { count: 0, errors: [] };
            }

            console.log(`Received ${backendAccounts.length} accounts from backend`);

            // Upsert each account (handles insert or update based on updated_at)
            for (const acc of backendAccounts) {
                await database.upsertAccount(acc);
                downloadedCount++;
            }

            // Mark all as synced
            const syncedIds = backendAccounts.map(a => a.id);
            await database.markAccountsAsSynced(syncedIds);
            syncedIds.forEach(id => this.lastSyncedAccountIds.add(id));

        } catch (error: any) {
            errors.push(`Account download error: ${error.message}`);
        }

        return { count: downloadedCount, errors };
    }

    // ==================== TRANSACTION SYNC ====================

    /**
     * Upload local transactions to backend (only new ones)
     */
    private async uploadTransactionsToBackend(): Promise<{ count: number; errors: string[] }> {
        const errors: string[] = [];
        let uploadedCount = 0;

        try {
            const localTransactions = await database.exportAllTransactions();

            if (localTransactions.length === 0) {
                return { count: 0, errors: [] };
            }

            const newTransactions = localTransactions.filter(
                t => t.Id && !this.lastSyncedIds.has(t.Id)
            );

            if (newTransactions.length === 0) {
                console.log('No new transactions to upload');
                return { count: 0, errors: [] };
            }

            console.log(`Uploading ${newTransactions.length} new transactions...`);

            const fileGroups = new Map<string, Transaction[]>();
            newTransactions.forEach(t => {
                const filename = t.filename || 'manual_entry.csv';
                if (!fileGroups.has(filename)) {
                    fileGroups.set(filename, []);
                }
                fileGroups.get(filename)!.push(t);
            });

            for (const [filename, transactions] of fileGroups) {
                try {
                    const csvContent = this.transactionsToCSV(transactions);
                    const formData = new FormData();
                    const base64Content = base64.encode(csvContent);
                    const fileObject: any = {
                        uri: `data:text/csv;base64,${base64Content}`,
                        type: 'text/csv',
                        name: filename,
                    };

                    formData.append('file', fileObject);

                    const response = await fetch(`${this.baseUrl}/api/upload-csv`, {
                        method: 'POST',
                        body: formData,
                        headers: {
                            'Content-Type': 'multipart/form-data',
                        },
                    });

                    if (response.ok) {
                        uploadedCount += transactions.length;
                        const syncedIds: number[] = [];
                        transactions.forEach(t => {
                            if (t.Id) {
                                this.lastSyncedIds.add(t.Id);
                                syncedIds.push(t.Id);
                            }
                        });

                        if (syncedIds.length > 0) {
                            await database.markTransactionsAsSynced(syncedIds);
                        }
                    } else {
                        const errorText = await response.text().catch(() => 'Unknown error');
                        errors.push(`Failed to upload ${filename}: ${errorText}`);
                    }
                } catch (error: any) {
                    errors.push(`Error uploading ${filename}: ${error.message}`);
                }
            }
        } catch (error: any) {
            errors.push(`Upload error: ${error.message}`);
        }

        return { count: uploadedCount, errors };
    }

    /**
     * Download transactions from backend
     */
    private async downloadTransactionsFromBackend(): Promise<{ count: number; errors: string[] }> {
        const errors: string[] = [];
        let downloadedCount = 0;

        try {
            const response = await fetch(`${this.baseUrl}/api/transactions?limit=10000`, {
                method: 'GET',
                headers: { 'Content-Type': 'application/json' },
            });

            if (!response.ok) {
                throw new Error('Failed to fetch transactions from backend');
            }

            const result = await response.json();
            const backendTransactions: Transaction[] = result.data || [];

            if (backendTransactions.length === 0) {
                return { count: 0, errors: [] };
            }

            const localTransactions = await database.exportAllTransactions();

            const localSignatures = new Set(
                localTransactions.map(t =>
                    `${t.Date}|${t.Details}|${t.Debit}|${t.Credit}|${t.Account_name}`
                )
            );

            const transactionsToInsert: Transaction[] = [];
            for (const t of backendTransactions) {
                const signature = `${t.Date}|${t.Details}|${t.Debit}|${t.Credit}|${t.Account_name}`;

                if (!localSignatures.has(signature)) {
                    const { Id, ...transactionWithoutId } = t;
                    transactionsToInsert.push(transactionWithoutId as Transaction);
                }
            }

            if (transactionsToInsert.length > 0) {
                console.log(`Downloading ${transactionsToInsert.length} new transactions...`);
                const insertedIds = await database.insertTransactions(transactionsToInsert);
                downloadedCount = insertedIds.length;

                if (insertedIds.length > 0) {
                    await database.markTransactionsAsSynced(insertedIds);
                    insertedIds.forEach(id => this.lastSyncedIds.add(id));
                }
            } else {
                console.log('No new transactions to download');
            }
        } catch (error: any) {
            errors.push(`Download error: ${error.message}`);
        }

        return { count: downloadedCount, errors };
    }

    // ==================== MAIN SYNC ====================

    /**
     * Perform full bidirectional sync of all tables
     * Order: Categories -> Accounts -> Transactions (due to dependencies)
     */
    async sync(): Promise<SyncResult> {
        const errors: string[] = [];
        const result: SyncResult = {
            success: false,
            transactions: { uploaded: 0, downloaded: 0 },
            categories: { uploaded: 0, downloaded: 0 },
            accounts: { uploaded: 0, downloaded: 0 },
            errors: [],
        };

        await this.loadSyncedIds();

        const isConnected = await this.checkConnection();
        if (!isConnected) {
            result.errors = ['Cannot connect to backend. Check URL and network connection.'];
            return result;
        }

        // 1. Sync Categories first (transactions may reference them)
        console.log('=== Syncing Categories ===');
        const catDownload = await this.downloadCategoriesFromBackend();
        const catUpload = await this.uploadCategoriesToBackend();
        result.categories = { uploaded: catUpload.count, downloaded: catDownload.count };
        errors.push(...catDownload.errors, ...catUpload.errors);

        // 2. Sync Accounts
        console.log('=== Syncing Accounts ===');
        const accDownload = await this.downloadAccountsFromBackend();
        const accUpload = await this.uploadAccountsToBackend();
        result.accounts = { uploaded: accUpload.count, downloaded: accDownload.count };
        errors.push(...accDownload.errors, ...accUpload.errors);

        // 3. Sync Transactions
        console.log('=== Syncing Transactions ===');
        const txUpload = await this.uploadTransactionsToBackend();
        const txDownload = await this.downloadTransactionsFromBackend();
        result.transactions = { uploaded: txUpload.count, downloaded: txDownload.count };
        errors.push(...txUpload.errors, ...txDownload.errors);

        result.success = errors.length === 0;
        result.errors = errors;

        console.log('=== Sync Complete ===');
        console.log(`Categories: ${result.categories.downloaded} down, ${result.categories.uploaded} up`);
        console.log(`Accounts: ${result.accounts.downloaded} down, ${result.accounts.uploaded} up`);
        console.log(`Transactions: ${result.transactions.downloaded} down, ${result.transactions.uploaded} up`);

        return result;
    }

    /**
     * Reset sync state (useful for debugging or fresh sync)
     */
    async resetSyncState(): Promise<void> {
        this.lastSyncedIds.clear();
        this.lastSyncedCategoryIds.clear();
        this.lastSyncedAccountIds.clear();
        console.warn('resetSyncState called but DB sync state is persistent. Use specialized method to clear DB if needed.');
    }

    /**
     * Convert transactions to CSV format
     */
    private transactionsToCSV(transactions: Transaction[]): string {
        const headers = ['Date', 'Details', 'Debit', 'Credit', 'Account_name', 'Category', 'Notes'];
        const rows = [headers.join(',')];

        transactions.forEach(t => {
            const row = [
                t.Date || '',
                `"${(t.Details || '').replace(/"/g, '""')}"`,
                t.Debit?.toString() || '',
                t.Credit?.toString() || '',
                t.Account_name || '',
                t.Category || '',
                `"${(t.Notes || '').replace(/"/g, '""')}"`,
            ];
            rows.push(row.join(','));
        });

        return rows.join('\n');
    }
}

// Create singleton instance
export const syncService = new SyncService();
