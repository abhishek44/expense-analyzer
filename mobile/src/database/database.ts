import * as SQLite from 'expo-sqlite';

// Types matching the backend Transaction model
export interface Transaction {
    Id?: number;
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
    Notes: string | null;
}

export interface UploadedFileRecord {
    id: number;
    filename: string;
    file_hash: string;
    upload_datetime: string;
    transaction_count: number;
}

export enum AccountType {
    SAVINGS = 'SAVINGS',
    CURRENT = 'CURRENT',
    CREDIT_CARD = 'CREDIT_CARD',
    CASH = 'CASH',
    WALLET = 'WALLET',
    INVESTMENT = 'INVESTMENT'
}

export interface Account {
    id: string;                // UUID
    name: string;
    account_type: AccountType;
    currency: string;          // Default: 'INR'
    opening_balance: number;   // Default: 0
    is_archived: number;       // 0 or 1
    created_at: string;        // ISO timestamp
    updated_at: string;        // ISO timestamp
}

export enum ReviewStatus {
    PENDING = 'pending',
    REVIEWED = 'reviewed',
}

class Database {
    private db: SQLite.SQLiteDatabase | null = null;
    private initPromise: Promise<void> | null = null;
    private isInitialized: boolean = false;

    /**
     * Initialize database and create tables
     */
    async init(): Promise<void> {
        // Return existing promise if already initializing
        if (this.initPromise) {
            return this.initPromise;
        }

        // Return immediately if already initialized
        if (this.isInitialized && this.db) {
            return Promise.resolve();
        }

        // Create new initialization promise
        this.initPromise = (async () => {
            try {
                // Use useNewConnection to avoid NullPointerException issues on some Android devices
                this.db = await SQLite.openDatabaseAsync('expense_analyzer.db', {
                    useNewConnection: true
                });
                await this.createTables();
                this.isInitialized = true;
                console.log('Database initialized successfully');
            } catch (error) {
                console.error('Failed to initialize database:', error);
                this.initPromise = null; // Reset so it can be retried
                throw error;
            }
        })();

        return this.initPromise;
    }

    /**
     * Create database tables
     */
    private async createTables(): Promise<void> {
        if (!this.db) throw new Error('Database not initialized');

        const createTableSQL = `
            CREATE TABLE IF NOT EXISTS transactions (
                Id INTEGER PRIMARY KEY AUTOINCREMENT,
                Date TEXT,
                Details TEXT,
                Debit REAL,
                Credit REAL,
                Account_name TEXT,
                Account_type TEXT,
                account_id TEXT,
                filename TEXT,
                review_status TEXT DEFAULT 'pending',
                review_datetime TEXT,
                uploaded_datetime TEXT,
                Category TEXT,
                Notes TEXT
            );
            
            CREATE TABLE IF NOT EXISTS uploaded_files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT NOT NULL,
                file_hash TEXT NOT NULL,
                upload_datetime TEXT,
                transaction_count INTEGER
            );

            CREATE INDEX IF NOT EXISTS idx_uploaded_files_hash ON uploaded_files(file_hash);

            CREATE TABLE IF NOT EXISTS synced_transactions (
                local_id INTEGER PRIMARY KEY,
                synced_at TEXT
            );

            CREATE TABLE IF NOT EXISTS accounts (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                account_type TEXT NOT NULL CHECK (
                    account_type IN ('SAVINGS','CURRENT','CREDIT_CARD','CASH','WALLET','INVESTMENT')
                ),
                currency TEXT NOT NULL DEFAULT 'INR',
                opening_balance REAL NOT NULL DEFAULT 0,
                is_archived INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_accounts_type ON accounts(account_type);
        `;

        await this.db.execAsync(createTableSQL);

        // Migration: Add Account_type column if it doesn't exist
        try {
            await this.db.execAsync('ALTER TABLE transactions ADD COLUMN Account_type TEXT');
            console.log('Added Account_type column');
        } catch (error: any) {
            // Ignore error if column already exists
            if (!error.message?.includes('duplicate column name')) {
                console.log('Migration note: Account_type column might already exist or failed to add:', error.message);
            }
        }

        // Migration: Add account_id column to transactions if it doesn't exist
        try {
            await this.db.execAsync('ALTER TABLE transactions ADD COLUMN account_id TEXT');
            console.log('Added account_id column');
        } catch (error: any) {
            // Ignore error if column already exists
            if (!error.message?.includes('duplicate column name')) {
                console.log('Migration note: account_id column might already exist or failed to add:', error.message);
            }
        }

        console.log('Tables created successfully');
    }

    /**
     * Ensure database is initialized before operations
     */
    private async ensureInit(): Promise<void> {
        if (!this.isInitialized || !this.db) {
            await this.init();
            return;
        }

        // Verify the connection is still valid by trying a simple query
        try {
            await this.db.execAsync('SELECT 1');
        } catch (error) {
            console.warn('Database connection invalid, reinitializing...');
            this.isInitialized = false;
            this.initPromise = null;
            this.db = null;
            await this.init();
        }
    }

    /**
     * Insert a single transaction
     */
    async insertTransaction(transaction: Transaction): Promise<number> {
        await this.ensureInit();
        if (!this.db) throw new Error('Database not initialized');

        const result = await this.db.runAsync(
            `INSERT INTO transactions (
                Date, Details, Debit, Credit, Account_name, Account_type, filename,
                review_status, review_datetime, uploaded_datetime, Category, Notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
            [
                transaction.Date,
                transaction.Details,
                transaction.Debit,
                transaction.Credit,
                transaction.Account_name,
                transaction.Account_type,
                transaction.filename,
                transaction.review_status || ReviewStatus.PENDING,
                transaction.review_datetime,
                transaction.uploaded_datetime,
                transaction.Category,
                transaction.Notes,
            ]
        );

        return result.lastInsertRowId;
    }

    /**
     * Insert multiple transactions (bulk insert)
     */
    async insertTransactions(transactions: Transaction[]): Promise<number[]> {
        await this.ensureInit();
        if (!this.db) throw new Error('Database not initialized');

        const insertedIds: number[] = [];

        await this.db.withTransactionAsync(async () => {
            for (const transaction of transactions) {
                const id = await this.insertTransaction(transaction);
                insertedIds.push(id);
            }
        });

        return insertedIds;
    }

    async getFilterOptions(): Promise<{ accountNames: string[]; accountTypes: string[] }> {
        await this.ensureInit();
        if (!this.db) throw new Error('Database not initialized');

        const names = await this.db.getAllAsync<{ Account_name: string }>('SELECT DISTINCT Account_name FROM transactions WHERE Account_name IS NOT NULL AND Account_name != "" ORDER BY Account_name');
        const types = await this.db.getAllAsync<{ Account_type: string }>('SELECT DISTINCT Account_type FROM transactions WHERE Account_type IS NOT NULL AND Account_type != "" ORDER BY Account_type');

        return {
            accountNames: names.map(n => n.Account_name),
            accountTypes: types.map(t => t.Account_type)
        };
    }

    /**
     * Get all transactions with optional filters
     */
    async getTransactions(
        statusFilter?: string,
        filenameFilter?: string,
        accountName?: string,
        accountType?: string,
        limit: number = 500
    ): Promise<Transaction[]> {
        await this.ensureInit();
        if (!this.db) throw new Error('Database not initialized');

        let query = 'SELECT * FROM transactions WHERE 1=1';
        const params: any[] = [];

        if (statusFilter) {
            query += ' AND review_status = ?';
            params.push(statusFilter);
        }

        if (filenameFilter) {
            query += ' AND filename = ?';
            params.push(filenameFilter);
        }

        if (accountName) {
            query += ' AND Account_name LIKE ?';
            params.push(`%${accountName}%`);
        }

        if (accountType) {
            query += ' AND Account_type LIKE ?';
            params.push(`%${accountType}%`);
        }

        query += ' ORDER BY Id DESC LIMIT ?';
        params.push(limit);

        const result = await this.db.getAllAsync<Transaction>(query, params);
        return result;
    }

    /**
     * Get a single transaction by ID
     */
    async getTransaction(id: number): Promise<Transaction | null> {
        await this.ensureInit();
        if (!this.db) throw new Error('Database not initialized');

        const result = await this.db.getFirstAsync<Transaction>(
            'SELECT * FROM transactions WHERE Id = ?',
            [id]
        );

        return result || null;
    }

    /**
     * Update a transaction
     */
    async updateTransaction(id: number, updates: Partial<Transaction>): Promise<void> {
        await this.ensureInit();
        if (!this.db) throw new Error('Database not initialized');

        const fields: string[] = [];
        const values: any[] = [];

        Object.entries(updates).forEach(([key, value]) => {
            if (key !== 'Id') {
                fields.push(`${key} = ?`);
                values.push(value);
            }
        });

        if (fields.length === 0) return;

        values.push(id);

        await this.db.runAsync(
            `UPDATE transactions SET ${fields.join(', ')} WHERE Id = ?`,
            values
        );
    }

    /**
     * Review a transaction (mark as reviewed with category)
     */
    async reviewTransaction(
        id: number,
        category: string,
        notes?: string
    ): Promise<void> {
        await this.ensureInit();
        if (!this.db) throw new Error('Database not initialized');

        await this.db.runAsync(
            `UPDATE transactions 
             SET Category = ?, Notes = ?, review_status = ?, review_datetime = ?
             WHERE Id = ?`,
            [category, notes || null, ReviewStatus.REVIEWED, new Date().toISOString(), id]
        );
    }

    /**
     * Delete transactions by filename
     */
    async deleteTransactionsByFilename(filename: string): Promise<number> {
        await this.ensureInit();
        if (!this.db) throw new Error('Database not initialized');

        const result = await this.db.runAsync(
            'DELETE FROM transactions WHERE filename = ?',
            [filename]
        );

        return result.changes;
    }

    /**
     * Delete a single transaction by ID
     */
    async deleteTransaction(id: number): Promise<void> {
        await this.ensureInit();
        if (!this.db) throw new Error('Database not initialized');

        await this.db.runAsync('DELETE FROM transactions WHERE Id = ?', [id]);
    }

    /**
     * Clear all transactions
     */
    async clearAllTransactions(): Promise<number> {
        await this.ensureInit();
        if (!this.db) throw new Error('Database not initialized');

        const result = await this.db.runAsync('DELETE FROM transactions');
        return result.changes;
    }

    /**
     * Get transaction count
     */
    async getTransactionCount(): Promise<number> {
        await this.ensureInit();
        if (!this.db) throw new Error('Database not initialized');

        const result = await this.db.getFirstAsync<{ count: number }>(
            'SELECT COUNT(*) as count FROM transactions'
        );

        return result?.count || 0;
    }

    /**
     * Get transaction counts by status
     */
    async getTransactionStats(): Promise<{
        total: number;
        pending: number;
        reviewed: number;
    }> {
        await this.ensureInit();
        if (!this.db) throw new Error('Database not initialized');

        const total = await this.getTransactionCount();

        const pendingResult = await this.db.getFirstAsync<{ count: number }>(
            'SELECT COUNT(*) as count FROM transactions WHERE review_status = ?',
            [ReviewStatus.PENDING]
        );

        const reviewedResult = await this.db.getFirstAsync<{ count: number }>(
            'SELECT COUNT(*) as count FROM transactions WHERE review_status = ?',
            [ReviewStatus.REVIEWED]
        );

        return {
            total,
            pending: pendingResult?.count || 0,
            reviewed: reviewedResult?.count || 0,
        };
    }

    /**
     * Get list of uploaded files with metadata
     */
    async getUploadedFiles(): Promise<
        Array<{
            filename: string;
            record_count: number;
            pending_count: number;
            reviewed_count: number;
            uploaded_at: string | null;
        }>
    > {
        await this.ensureInit();
        if (!this.db) throw new Error('Database not initialized');

        const query = `
            SELECT 
                filename,
                COUNT(*) as record_count,
                SUM(CASE WHEN review_status = 'pending' THEN 1 ELSE 0 END) as pending_count,
                SUM(CASE WHEN review_status = 'reviewed' THEN 1 ELSE 0 END) as reviewed_count,
                MIN(uploaded_datetime) as uploaded_at
            FROM transactions
            GROUP BY filename
        `;

        const result = await this.db.getAllAsync<any>(query);
        return result;
    }

    /**
     * Export all transactions to array (for CSV export)
     */
    async exportAllTransactions(): Promise<Transaction[]> {
        await this.ensureInit();
        if (!this.db) throw new Error('Database not initialized');

        const result = await this.db.getAllAsync<Transaction>(
            'SELECT * FROM transactions ORDER BY Date ASC'
        );

        return result;
    }

    /**
     * Check if a file with the same hash exists
     */
    async checkFileExists(fileHash: string): Promise<UploadedFileRecord | null> {
        await this.ensureInit();
        if (!this.db) throw new Error('Database not initialized');

        const result = await this.db.getFirstAsync<UploadedFileRecord>(
            'SELECT * FROM uploaded_files WHERE file_hash = ?',
            [fileHash]
        );

        return result || null;
    }

    /**
     * Get file by filename (to check for filename duplicates if needed)
     */
    async getFileByFilename(filename: string): Promise<UploadedFileRecord | null> {
        await this.ensureInit();
        if (!this.db) throw new Error('Database not initialized');

        const result = await this.db.getFirstAsync<UploadedFileRecord>(
            'SELECT * FROM uploaded_files WHERE filename = ?',
            [filename]
        );

        return result || null;
    }

    /**
     * Record a new uploaded file
     */
    async insertUploadedFile(
        filename: string,
        fileHash: string,
        transactionCount: number
    ): Promise<void> {
        await this.ensureInit();
        if (!this.db) throw new Error('Database not initialized');

        await this.db.runAsync(
            `INSERT INTO uploaded_files (
                filename, file_hash, upload_datetime, transaction_count
            ) VALUES (?, ?, ?, ?)`,
            [filename, fileHash, new Date().toISOString(), transactionCount]
        );
    }

    /**
     * Mark transactions as synced
     */
    async markTransactionsAsSynced(ids: number[]): Promise<void> {
        await this.ensureInit();
        if (!this.db) throw new Error('Database not initialized');

        const syncedAt = new Date().toISOString();

        await this.db.withTransactionAsync(async () => {
            for (const id of ids) {
                await this.db!.runAsync(
                    'INSERT OR REPLACE INTO synced_transactions (local_id, synced_at) VALUES (?, ?)',
                    [id, syncedAt]
                );
            }
        });
    }

    /**
     * Get all synced transaction IDs
     */
    async getSyncedTransactionIds(): Promise<number[]> {
        await this.ensureInit();
        if (!this.db) throw new Error('Database not initialized');

        const result = await this.db.getAllAsync<{ local_id: number }>(
            'SELECT local_id FROM synced_transactions'
        );

        return result.map(r => r.local_id);
    }

    // ==================== ACCOUNT METHODS ====================

    /**
     * Generate a UUID for accounts
     */
    private generateUUID(): string {
        return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
            const r = (Math.random() * 16) | 0;
            const v = c === 'x' ? r : (r & 0x3) | 0x8;
            return v.toString(16);
        });
    }

    /**
     * Create a new account
     */
    async createAccount(account: Omit<Account, 'id' | 'created_at' | 'updated_at'>): Promise<string> {
        await this.ensureInit();
        if (!this.db) throw new Error('Database not initialized');

        const id = this.generateUUID();
        const now = new Date().toISOString();

        await this.db.runAsync(
            `INSERT INTO accounts (id, name, account_type, currency, opening_balance, is_archived, created_at, updated_at)
             VALUES (?, ?, ?, ?, ?, ?, ?, ?)`,
            [
                id,
                account.name,
                account.account_type,
                account.currency || 'INR',
                account.opening_balance || 0,
                account.is_archived || 0,
                now,
                now
            ]
        );

        return id;
    }

    /**
     * Get all accounts (non-archived by default)
     */
    async getAccounts(includeArchived: boolean = false): Promise<Account[]> {
        await this.ensureInit();
        if (!this.db) throw new Error('Database not initialized');

        let query = 'SELECT * FROM accounts';
        if (!includeArchived) {
            query += ' WHERE is_archived = 0';
        }
        query += ' ORDER BY name ASC';

        const result = await this.db.getAllAsync<Account>(query);
        return result;
    }

    /**
     * Get a single account by ID
     */
    async getAccount(id: string): Promise<Account | null> {
        await this.ensureInit();
        if (!this.db) throw new Error('Database not initialized');

        const result = await this.db.getFirstAsync<Account>(
            'SELECT * FROM accounts WHERE id = ?',
            [id]
        );

        return result || null;
    }

    /**
     * Update an account
     */
    async updateAccount(id: string, updates: Partial<Omit<Account, 'id' | 'created_at'>>): Promise<void> {
        await this.ensureInit();
        if (!this.db) throw new Error('Database not initialized');

        const fields: string[] = [];
        const values: any[] = [];

        Object.entries(updates).forEach(([key, value]) => {
            if (key !== 'id' && key !== 'created_at') {
                fields.push(`${key} = ?`);
                values.push(value);
            }
        });

        if (fields.length === 0) return;

        // Always update the updated_at timestamp
        fields.push('updated_at = ?');
        values.push(new Date().toISOString());

        values.push(id);

        await this.db.runAsync(
            `UPDATE accounts SET ${fields.join(', ')} WHERE id = ?`,
            values
        );
    }

    /**
     * Delete an account
     */
    async deleteAccount(id: string): Promise<void> {
        await this.ensureInit();
        if (!this.db) throw new Error('Database not initialized');

        await this.db.runAsync('DELETE FROM accounts WHERE id = ?', [id]);
    }

    /**
     * Get account balance (opening_balance + sum of transactions)
     */
    async getAccountBalance(id: string): Promise<number> {
        await this.ensureInit();
        if (!this.db) throw new Error('Database not initialized');

        // Get the account
        const account = await this.getAccount(id);
        if (!account) return 0;

        // Get sum of transactions for this account
        const creditResult = await this.db.getFirstAsync<{ total: number | null }>(
            'SELECT SUM(Credit) as total FROM transactions WHERE account_id = ?',
            [id]
        );
        const debitResult = await this.db.getFirstAsync<{ total: number | null }>(
            'SELECT SUM(Debit) as total FROM transactions WHERE account_id = ?',
            [id]
        );

        const credits = creditResult?.total || 0;
        const debits = debitResult?.total || 0;

        return account.opening_balance + credits - debits;
    }

    /**
     * Get all accounts with their computed balances
     */
    async getAccountsWithBalances(): Promise<Array<Account & { balance: number }>> {
        await this.ensureInit();
        if (!this.db) throw new Error('Database not initialized');

        const accounts = await this.getAccounts();
        const accountsWithBalances = await Promise.all(
            accounts.map(async (account) => {
                const balance = await this.getAccountBalance(account.id);
                return { ...account, balance };
            })
        );

        return accountsWithBalances;
    }
}

// Create singleton instance
export const database = new Database();

