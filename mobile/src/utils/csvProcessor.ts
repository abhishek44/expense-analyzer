import Papa from 'papaparse';
import * as Crypto from 'expo-crypto';
import { Transaction, ReviewStatus } from '../database/database';

// Column mapping from CSV headers to Transaction model fields
// Strict Column mapping from CSV headers to Transaction model fields
const TRANSACTION_COLUMN_MAPPING: Record<string, string> = {
    'Date': 'Date',
    'Details': 'Details',
    'Debit': 'Debit',
    'Credit': 'Credit',
    'AccountName': 'Account_name',
    'AccountType': 'Account_type',
    'Category': 'Category',
    'Notes': 'Notes',
    'ReviewStatus': 'review_status',
    'ReviewdateTime': 'review_datetime',
};

/**
 * Parse float value from string
 */
function parseFloat(value: string): number | null {
    if (!value || !value.trim()) {
        return null;
    }
    try {
        return Number(value.trim().replace(/,/g, ''));
    } catch {
        return null;
    }
}

/**
 * Check if CSV headers match strict transaction format
 */
function isStrictFormat(headers: string[]): boolean {
    const expectedColumns = new Set(Object.keys(TRANSACTION_COLUMN_MAPPING));
    const currentHeaders = new Set(headers);

    // Check if all expected columns are present
    for (const expected of expectedColumns) {
        if (!currentHeaders.has(expected)) {
            return false;
        }
    }
    return true;
}

/**
 * Parse date for sorting
 */
function parseDateForSort(dateStr: string | null): Date {
    if (!dateStr) return new Date(0);

    const formats = [
        // DD-MMM-YY (e.g., 17-Dec-24)
        /^(\d{1,2})-([A-Za-z]{3})-(\d{2})$/,
        // YYYY-MM-DD
        /^(\d{4})-(\d{1,2})-(\d{1,2})$/,
        // DD/MM/YYYY
        /^(\d{1,2})\/(\d{1,2})\/(\d{4})$/,
        // MM/DD/YYYY
        /^(\d{1,2})\/(\d{1,2})\/(\d{4})$/,
        // DD-MM-YYYY
        /^(\d{1,2})-(\d{1,2})-(\d{4})$/,
    ];

    const monthMap: Record<string, number> = {
        jan: 0, feb: 1, mar: 2, apr: 3, may: 4, jun: 5,
        jul: 6, aug: 7, sep: 8, oct: 9, nov: 10, dec: 11,
    };

    try {
        // Try DD-MMM-YY format first
        const match1 = dateStr.match(formats[0]);
        if (match1) {
            const day = parseInt(match1[1]);
            const month = monthMap[match1[2].toLowerCase()];
            let year = parseInt(match1[3]);
            year = year < 50 ? 2000 + year : 1900 + year;
            return new Date(year, month, day);
        }

        // Try other formats
        const date = new Date(dateStr);
        if (!isNaN(date.getTime())) {
            return date;
        }
    } catch {
        // Ignore parsing errors
    }

    return new Date(0);
}

/**
 * Process CSV content and return transactions
 */
export async function processCSV(
    csvContent: string,
    filename: string,
    accountName?: string
): Promise<{
    transactions: Transaction[];
    rowsInserted: number;
    formatConverted: boolean;
}> {
    return new Promise((resolve, reject) => {
        Papa.parse(csvContent, {
            header: true,
            skipEmptyLines: true,
            complete: (results) => {
                try {
                    const headers = results.meta.fields || [];
                    const rows = results.data as Record<string, string>[];

                    if (headers.length === 0) {
                        reject(new Error('CSV file has no headers'));
                        return;
                    }

                    if (rows.length === 0) {
                        reject(new Error('CSV file has no data rows'));
                        return;
                    }

                    if (!isStrictFormat(headers)) {
                        const missing = Object.keys(TRANSACTION_COLUMN_MAPPING).filter(c => !headers.includes(c));
                        reject(new Error(`Invalid CSV format. Missing columns: ${missing.join(', ')}`));
                        return;
                    }

                    const uploadTime = new Date();
                    const transactionsToInsert: Transaction[] = [];

                    for (const row of rows) {
                        const mappedData: Partial<Transaction> = {
                            filename,
                            uploaded_datetime: uploadTime.toISOString(),
                        };

                        // Strict mapping
                        for (const [csvHeader, modelField] of Object.entries(TRANSACTION_COLUMN_MAPPING)) {
                            const value = row[csvHeader]?.trim() || null;

                            if (modelField === 'Debit' || modelField === 'Credit') {
                                (mappedData as any)[modelField] = value ? parseFloat(value) : null;
                            } else {
                                (mappedData as any)[modelField] = value;
                            }
                        }

                        // Override account name if provided via args (though CSV has it now)
                        if (accountName && !mappedData.Account_name) {
                            mappedData.Account_name = accountName;
                        }

                        transactionsToInsert.push(mappedData as Transaction);
                    }

                    // Sort transactions by date in ascending order
                    transactionsToInsert.sort((a, b) => {
                        const dateA = parseDateForSort(a.Date);
                        const dateB = parseDateForSort(b.Date);
                        return dateA.getTime() - dateB.getTime();
                    });

                    resolve({
                        transactions: transactionsToInsert,
                        rowsInserted: transactionsToInsert.length,
                        formatConverted: false,
                    });
                } catch (error: any) {
                    reject(error);
                }
            },
            error: (error: any) => {
                reject(new Error(`CSV parsing error: ${error.message}`));
            },
        });
    });
}

// Keep helper functions for file reading and hashing as is
/**
 * Read CSV file from URI
 */
export async function readCSVFile(fileUri: string): Promise<string> {
    try {
        const response = await fetch(fileUri);
        const text = await response.text();
        return text;
    } catch (error: any) {
        throw new Error(`Failed to read CSV file: ${error}`);
    }
}

/**
 * Calculate SHA-256 hash of file content
 */
export async function calculateFileHash(content: string): Promise<string> {
    try {
        const hash = await Crypto.digestStringAsync(
            Crypto.CryptoDigestAlgorithm.SHA256,
            content
        );
        return hash;
    } catch (error) {
        console.error('Error calculating hash:', error);
        // Fallback or rethrow
        throw new Error('Failed to calculate file hash');
    }
}

