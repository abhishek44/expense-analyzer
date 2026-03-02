import { database, Transaction as DBTransaction, ReviewStatus } from '../database/database';
import { processCSV, readCSVFile, calculateFileHash } from '../utils/csvProcessor';

// Types matching the backend models (keep for compatibility)
export interface Transaction {
    Id: number;
    Date: string | null;
    Details: string | null;
    Debit: number | null;
    Credit: number | null;
    Account_name: string | null;
    Account_type: string | null;
    filename: string;
    review_status: string;
    review_datetime: string | null;
    uploaded_datetime: string | null;
    Category: string | null;
    category_id?: string | null;
    Notes: string | null;
}

export interface Category {
    id: string;
    name: string;
    type: 'INCOME' | 'EXPENSE';
    icon?: string;
    color?: string;
    is_archived: number;
}

export interface UploadedFile {
    filename: string;
    record_count: number;
    pending_count: number;
    reviewed_count: number;
    account_name: string | null;
    account_type: string | null;
    uploaded_at: string | null;
}

export interface TableInfo {
    name: string;
    total: number;
    pending?: number;
    reviewed?: number;
}

// API Response types
interface ApiResponse<T> {
    success?: boolean;
    data?: T;
    error?: string;
    detail?: string;
}

class ApiClient {
    private initialized: boolean = false;

    /**
     * Initialize the database
     */
    async init(): Promise<void> {
        if (!this.initialized) {
            await database.init();
            this.initialized = true;
            console.log('Offline database initialized');
        }
    }

    /**
     * Ensure database is initialized before operations
     */
    private async ensureInit(): Promise<void> {
        if (!this.initialized) {
            await this.init();
        }
    }

    /**
     * Upload CSV file (now processes locally)
     */
    async uploadCSV(
        fileUri: string,
        fileName: string,
        accountName?: string,
        forceUpload: boolean = false
    ): Promise<{
        success: boolean;
        rows_inserted?: number;
        message?: string;
        isDuplicate?: boolean;
        duplicateInfo?: {
            uploadDate: string;
            transactionCount: number;
        };
    }> {
        try {
            await this.ensureInit();

            // Read CSV file content
            const csvContent = await readCSVFile(fileUri);

            // Calculate hash for duplicate detection
            const fileHash = await calculateFileHash(csvContent);

            // Check for duplicates (BOTH filename and hash must match)
            if (!forceUpload) {
                const existingHashRequest = await database.checkFileExists(fileHash);
                const existingFilenameRequest = await database.getFileByFilename(fileName);

                // Check if we have a record that matches both
                // We check if the record found by hash has the same filename
                if (existingHashRequest && existingHashRequest.filename === fileName) {
                    return {
                        success: false,
                        message: 'Duplicate file detected',
                        isDuplicate: true,
                        duplicateInfo: {
                            uploadDate: existingHashRequest.upload_datetime,
                            transactionCount: existingHashRequest.transaction_count
                        }
                    };
                }
            }

            // Process CSV
            const result = await processCSV(csvContent, fileName, accountName);

            // Insert transactions into local database
            const insertedIds = await database.insertTransactions(result.transactions);
            const insertedCount = insertedIds.length;

            // Record the uploaded file
            await database.insertUploadedFile(fileName, fileHash, insertedCount);

            let message = `Successfully uploaded ${insertedCount} rows`;
            if (result.formatConverted) {
                message += ' (CSV format was converted)';
            }

            return {
                success: true,
                rows_inserted: insertedCount,
                message,
            };
        } catch (error: any) {
            console.error('Upload CSV error:', error);
            return {
                success: false,
                message: error.message || 'Failed to upload CSV',
            };
        }
    }

    /**
     * Get tables with stats
     */
    async getTables(): Promise<{ tables: TableInfo[] }> {
        await this.ensureInit();

        const stats = await database.getTransactionStats();

        return {
            tables: [
                {
                    name: 'transactions',
                    description: 'Transaction records',
                    total: stats.total,
                    pending: stats.pending,
                    reviewed: stats.reviewed,
                    uploadable: true,
                } as any,
            ],
        };
    }

    /**
     * Get uploaded files
     */
    async getUploadedFiles(): Promise<{ files: UploadedFile[] }> {
        await this.ensureInit();

        const files = await database.getUploadedFiles();

        return {
            files: files.map(f => ({
                filename: f.filename,
                record_count: f.record_count,
                pending_count: f.pending_count,
                reviewed_count: f.reviewed_count,
                account_name: null,
                account_type: null,
                uploaded_at: f.uploaded_at,
            })),
        };
    }

    /**
     * Delete file records
     */
    async deleteFile(filename: string): Promise<{ success: boolean; message: string }> {
        await this.ensureInit();

        const count = await database.deleteTransactionsByFilename(filename);

        if (count === 0) {
            return {
                success: false,
                message: `No records found for file '${filename}'`,
            };
        }

        return {
            success: true,
            message: `Deleted ${count} records for file '${filename}'`,
        };
    }

    /**
     * Get transactions
     */
    async deleteTransaction(id: number): Promise<{ success: boolean; message: string }> {
        await this.ensureInit();
        await database.deleteTransaction(id);
        return { success: true, message: 'Transaction deleted' };
    }

    /**
     * Get transactions
     */
    async getTransactions(
        statusFilter?: string,
        filenameFilter?: string,
        accountName?: string,
        accountType?: string,
        categoryId?: string,
        limit: number = 100,
        skip: number = 0,
        dateFrom?: string,
        dateTo?: string
    ): Promise<{ data: Transaction[]; total: number }> {
        await this.ensureInit();

        const [transactions, total] = await Promise.all([
            database.getTransactions(
                statusFilter,
                filenameFilter,
                accountName,
                accountType,
                categoryId,
                limit,
                skip,
                dateFrom,
                dateTo
            ),
            database.getFilteredTransactionCount(
                statusFilter,
                filenameFilter,
                accountName,
                accountType,
                categoryId,
                dateFrom,
                dateTo
            )
        ]);

        return {
            data: transactions as Transaction[],
            total,
        };
    }

    async getFilterOptions(): Promise<{ accountNames: string[]; accountTypes: string[] }> {
        await this.ensureInit();
        return await database.getFilterOptions();
    }

    /**
     * Get single transaction
     */
    async getTransaction(id: number): Promise<Transaction> {
        await this.ensureInit();

        const transaction = await database.getTransaction(id);

        if (!transaction) {
            throw new Error('Transaction not found');
        }

        return transaction as Transaction;
    }

    /**
     * Review a transaction
     */
    async reviewTransaction(
        id: number,
        reviewData: {
            Category: string;
            categoryId?: string;
            Notes?: string;
        }
    ): Promise<{ success: boolean; transaction?: Transaction }> {
        await this.ensureInit();

        // If we have a category ID, use it. If not, maybe look it up by name?
        // For now, we update both if provided. The underlying DB method needs to support categoryId updates.
        // I need to update database.reviewTransaction to support category_id.
        // Wait, I didn't update database.reviewTransaction signature in previous step!
        // I only added createCategory etc.
        // Let me update database.reviewTransaction first or do a raw update here?
        // Better to use database.updateTransaction.

        await database.reviewTransaction(id, reviewData.Category, reviewData.Notes);

        if (reviewData.categoryId) {
            await database.updateTransaction(id, { category_id: reviewData.categoryId });
        }

        const transaction = await database.getTransaction(id);

        return {
            success: true,
            transaction: transaction as Transaction,
        };
    }

    /**
     * Create transaction manually
     */
    async createTransaction(data: {
        Date?: string;
        Details: string;
        Debit?: number;
        Credit?: number;
        Account_name: string;
        Account_type?: string;
        Category?: string;
        categoryId?: string;
        Notes?: string;
    }): Promise<{ success: boolean; transaction?: Transaction }> {
        await this.ensureInit();

        const transaction: DBTransaction = {
            Date: data.Date || new Date().toISOString().split('T')[0],
            Details: data.Details,
            Debit: data.Debit || null,
            Credit: data.Credit || null,
            Account_name: data.Account_name,
            Account_type: data.Account_type || 'Manual',
            filename: 'manual_entry',
            Category: data.Category || null,
            category_id: data.categoryId || null,
            Notes: data.Notes || null,
            review_status: data.Category ? ReviewStatus.REVIEWED : ReviewStatus.PENDING,
            review_datetime: data.Category ? new Date().toISOString() : null,
            uploaded_datetime: new Date().toISOString(),
        };

        const id = await database.insertTransaction(transaction);
        const createdTransaction = await database.getTransaction(id);

        return {
            success: true,
            transaction: createdTransaction as Transaction,
        };
    }

    /**
     * Clear table
     */
    async clearTable(tableName: string): Promise<{ success: boolean; message: string }> {
        await this.ensureInit();

        if (tableName === 'transactions') {
            const count = await database.clearAllTransactions();
            return {
                success: true,
                message: `Deleted ${count} records from transactions`,
            };
        } else {
            return {
                success: false,
                message: `Table '${tableName}' not found`,
            };
        }
    }

    /**
     * Export all transactions (for backup)
     */
    async exportTransactions(): Promise<Transaction[]> {
        await this.ensureInit();
        return (await database.exportAllTransactions()) as Transaction[];
    }


    // ==================== CATEGORY METHODS ====================

    /**
     * Get all categories
     */
    async getCategories(type?: 'INCOME' | 'EXPENSE'): Promise<Category[]> {
        await this.ensureInit();
        return await database.getCategories(type);
    }

    /**
     * Create a new category
     */
    async createCategory(data: { name: string; type: 'INCOME' | 'EXPENSE' }): Promise<{ success: boolean; id?: string; error?: string }> {
        try {
            await this.ensureInit();
            const id = await database.createCategory({
                name: data.name,
                type: data.type,
                color: '#137fec', // Default blue
                icon: 'category'
            });
            return { success: true, id };
        } catch (e: any) {
            return { success: false, error: e.message };
        }
    }

    async updateCategory(
        id: string,
        category: { name?: string; type?: 'INCOME' | 'EXPENSE' }
    ): Promise<{ success: boolean; error?: string }> {
        await this.ensureInit();
        try {
            await database.updateCategory(id, category);
            return { success: true };
        } catch (e: any) {
            console.error('Failed to update category', e);
            return { success: false, error: e.message };
        }
    }

    /**
     * Delete a category
     */
    async deleteCategory(id: string): Promise<{ success: boolean; message?: string }> {
        await this.ensureInit();
        await database.deleteCategory(id);
        return { success: true };
    }
}

// Export singleton instance
export const api = new ApiClient();

// Note: Database will be initialized lazily on first use via ensureInit()
// This prevents multiple initializations and follows best practices
