import { database, Transaction } from '../database/database';
import { storage } from '../api/storage';
import base64 from 'react-native-base64';

export interface SyncResult {
    success: boolean;
    uploaded: number;
    downloaded: number;
    errors: string[];
}

/**
 * Sync service for bidirectional sync with FastAPI backend
 */
class SyncService {
    private baseUrl: string = '';
    private lastSyncedIds: Set<number> = new Set();

    /**
     * Initialize sync service with backend URL
     */
    async init(): Promise<void> {
        this.baseUrl = await storage.getApiUrl();
        await this.loadSyncedIds();
    }

    /**
     * Load previously synced transaction IDs from database
     */
    private async loadSyncedIds(): Promise<void> {
        try {
            const syncedIds = await database.getSyncedTransactionIds();
            this.lastSyncedIds = new Set(syncedIds);
            console.log(`Loaded ${this.lastSyncedIds.size} synced transaction IDs from DB`);
        } catch (error) {
            console.error('Failed to load synced IDs:', error);
            // Fallback to empty, will be re-populated on next successful sync logic or full re-sync
            this.lastSyncedIds = new Set();
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

    /**
     * Upload local transactions to backend (only new ones)
     */
    private async uploadToBackend(): Promise<{ count: number; errors: string[] }> {
        const errors: string[] = [];
        let uploadedCount = 0;

        try {
            // Get all local transactions
            const localTransactions = await database.exportAllTransactions();

            if (localTransactions.length === 0) {
                return { count: 0, errors: [] };
            }

            // Filter out transactions that have already been synced
            const newTransactions = localTransactions.filter(
                t => t.Id && !this.lastSyncedIds.has(t.Id)
            );

            if (newTransactions.length === 0) {
                console.log('No new transactions to upload');
                return { count: 0, errors: [] };
            }

            console.log(`Uploading ${newTransactions.length} new transactions...`);

            // Group by filename for batch upload
            const fileGroups = new Map<string, Transaction[]>();
            newTransactions.forEach(t => {
                const filename = t.filename || 'manual_entry.csv';
                if (!fileGroups.has(filename)) {
                    fileGroups.set(filename, []);
                }
                fileGroups.get(filename)!.push(t);
            });

            // Upload each group
            for (const [filename, transactions] of fileGroups) {
                try {
                    // Create CSV content
                    const csvContent = this.transactionsToCSV(transactions);

                    // Use React Native compatible FormData
                    const formData = new FormData();

                    // Create file object for React Native
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
                        // Mark these transactions as synced in DB and memory
                        const syncedIds: number[] = [];
                        transactions.forEach(t => {
                            if (t.Id) {
                                this.lastSyncedIds.add(t.Id);
                                syncedIds.push(t.Id);
                            }
                        });

                        // Persist to DB
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
    private async downloadFromBackend(): Promise<{ count: number; errors: string[] }> {
        const errors: string[] = [];
        let downloadedCount = 0;

        try {
            // Fetch all transactions from backend
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

            // Get all local transaction IDs to avoid duplicates
            const localTransactions = await database.exportAllTransactions();

            // Create a set of local transaction signatures for duplicate detection
            const localSignatures = new Set(
                localTransactions.map(t =>
                    `${t.Date}|${t.Details}|${t.Debit}|${t.Credit}|${t.Account_name}`
                )
            );

            // Insert transactions that don't exist locally
            const transactionsToInsert: Transaction[] = [];
            for (const t of backendTransactions) {
                const signature = `${t.Date}|${t.Details}|${t.Debit}|${t.Credit}|${t.Account_name}`;

                if (!localSignatures.has(signature)) {
                    // Remove Id to let local DB auto-generate
                    const { Id, ...transactionWithoutId } = t;
                    transactionsToInsert.push(transactionWithoutId as Transaction);
                }
            }

            if (transactionsToInsert.length > 0) {
                console.log(`Downloading ${transactionsToInsert.length} new transactions...`);
                // Insert and get IDs of new transactions
                const insertedIds = await database.insertTransactions(transactionsToInsert);
                downloadedCount = insertedIds.length;

                // Mark these newly downloaded transactions as synced (so we don't re-upload them)
                if (insertedIds.length > 0) {
                    await database.markTransactionsAsSynced(insertedIds);
                    // Also update in-memory cache
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

    /**
     * Perform full bidirectional sync
     */
    async sync(): Promise<SyncResult> {
        const errors: string[] = [];

        // Ensure we have loaded synced IDs
        await this.loadSyncedIds();

        // Check connection first
        const isConnected = await this.checkConnection();
        if (!isConnected) {
            return {
                success: false,
                uploaded: 0,
                downloaded: 0,
                errors: ['Cannot connect to backend. Check URL and network connection.'],
            };
        }

        // Upload local transactions to backend (only new ones)
        const uploadResult = await this.uploadToBackend();
        errors.push(...uploadResult.errors);

        // Download backend transactions to local
        const downloadResult = await this.downloadFromBackend();
        errors.push(...downloadResult.errors);

        return {
            success: errors.length === 0,
            uploaded: uploadResult.count,
            downloaded: downloadResult.count,
            errors,
        };
    }

    /**
     * Reset sync state (useful for debugging or fresh sync)
     */
    async resetSyncState(): Promise<void> {
        this.lastSyncedIds.clear();
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
