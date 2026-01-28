// Utility functions for input validation

/**
 * Validate date string in YYYY-MM-DD format
 */
export function validateDate(dateString: string): boolean {
    if (!dateString) return false;

    const dateRegex = /^\d{4}-\d{2}-\d{2}$/;
    if (!dateRegex.test(dateString)) return false;

    const date = new Date(dateString);
    return date instanceof Date && !isNaN(date.getTime());
}

/**
 * Validate and sanitize amount input
 * Returns the sanitized string or null if invalid
 */
export function sanitizeAmount(amount: string): string | null {
    if (!amount) return null;

    // Remove all non-numeric characters except decimal point
    const sanitized = amount.replace(/[^\d.]/g, '');

    // Check for valid number format
    const numberRegex = /^\d+(\.\d{0,2})?$/;
    if (!numberRegex.test(sanitized)) return null;

    return sanitized;
}

/**
 * Validate URL format
 */
export function validateUrl(url: string): boolean {
    if (!url) return false;

    try {
        const urlObj = new URL(url);
        return urlObj.protocol === 'http:' || urlObj.protocol === 'https:';
    } catch {
        return false;
    }
}

/**
 * Format date from DD/MM/YYYY to YYYY-MM-DD
 */
export function formatDateDDMMYYYYtoISO(date: string): string | null {
    if (!date) return null;

    const parts = date.split('/');
    if (parts.length !== 3) return null;

    const [day, month, year] = parts;
    const isoDate = `${year}-${month.padStart(2, '0')}-${day.padStart(2, '0')}`;

    return validateDate(isoDate) ? isoDate : null;
}

/**
 * Get current date in YYYY-MM-DD format
 */
export function getCurrentDate(): string {
    return new Date().toISOString().split('T')[0];
}
