"""Transaction and attachment matching logic.

This module provides functions to match bank transactions with their corresponding
attachments (receipts, invoices) based on reference numbers, amounts, dates, and
counterparty names.
"""

from datetime import datetime

Attachment = dict[str, dict]
Transaction = dict[str, dict]

# Matching constants
AMOUNT_TOLERANCE = 0.01
DATE_TOLERANCE_DAYS = 15
MIN_COMMON_WORDS = 2
SCORE_AMOUNT = 1
SCORE_DATE = 1
SCORE_NAME = 1
MIN_SCORE_WITH_CONTACT = 3
MIN_SCORE_WITHOUT_CONTACT = 2


def normalize_reference(ref: str | None) -> str | None:
    """
    Normalize reference number by removing spaces and leading zeros.
    
    Args:
        ref: Raw reference number string
        
    Returns:
        Normalized reference number or None if invalid
    """
    if not ref or ref == 'None':
        return None
    
    normalized = str(ref).replace(' ', '').upper().lstrip('0')
    return normalized if normalized else None


def names_match(name1: str | None, name2: str | None) -> bool:
    """
    Check if two counterparty names match.
    
    Uses multiple strategies:
    - Exact match
    - Word-boundary subset match
    - Word overlap
    
    Args:
        name1: First name to compare
        name2: Second name to compare
        
    Returns:
        True if names match, else False
    """
    if not name1 or not name2:
        return False
    
    n1 = str(name1).lower().strip()
    n2 = str(name2).lower().strip()
    
    # exact match
    if n1 == n2:
        return True

    # split into word sets
    words1 = set(n1.split())
    words2 = set(n2.split())

    if not words1 or not words2:
        return False

    # subset match
    if words1.issubset(words2) or words2.issubset(words1):
        return True

    # common word overlap
    if len(words1) > 1 and len(words2) > 1:
        common_words = words1 & words2
        if len(common_words) >= MIN_COMMON_WORDS:
            return True

    return False


def _calculate_match_score(
    transaction_amount: float,
    transaction_date: datetime,
    transaction_contact: str,
    att_data: dict,
) -> int:
    """
    Calculate match score between transaction and attachment data.
    
    scoring approach:
    - Amount match [REQUIRED]: +1 point
    - Date within tolerance: +1 point
    - Name match: +1 point
    
    Args:
        transaction_amount: Transaction amount (absolute value)
        transaction_date: Transaction date
        transaction_contact: Transaction contact name
        att_data: Attachment data dictionary
        
    Returns:
        Match score (0-3)
    """
    score = 0   #initialize score with 0
    
    # AMOUNT must match exactly (within tolerance)
    att_amount = float(att_data['total_amount'])
    if abs(att_amount - transaction_amount) >= AMOUNT_TOLERANCE:
        return 0
    score += SCORE_AMOUNT
    
    # Date within tolerance window
    if att_data.get('due_date'):
        att_date = datetime.strptime(att_data['due_date'], '%Y-%m-%d')
        days_diff = abs((att_date - transaction_date).days)
        if days_diff <= DATE_TOLERANCE_DAYS:
            score += SCORE_DATE

    # NAME match (check all possible fields for name matching)
    att_names = [
        att_data.get('issuer'),
        att_data.get('recipient'),
        att_data.get('supplier'),
    ]
    if any(names_match(transaction_contact, name) for name in att_names if name):
        score += SCORE_NAME
    
    return score


def find_attachment(
    transaction: Transaction,
    attachments: list[Attachment],
) -> Attachment | None:
    """
    Find the best matching attachment for a given transaction.
    
    Matching strategy:
    - Reference number match (highest priority, always 1:1)
    - Amount + Date + Name combination (requires all 3 if contact exists)
    
    Args:
        transaction: Transaction dictionary with fields: id, date, amount, contact, reference
        attachments: List of attachment dictionaries
        
    Returns:
        Best matching attachment or None if no confident match found
    """
    # Priority 1: Reference number match (1:1 mapping)
    transaction_ref = normalize_reference(transaction.get('reference'))
    if transaction_ref:
        for att in attachments:
            att_data = att.get('data', att)
            att_ref = normalize_reference(att_data.get('reference'))
            if att_ref == transaction_ref:
                return att
    
    # Priority 2: Amount + Date + Name matching
    transaction_amount = abs(float(transaction['amount']))
    transaction_date = datetime.strptime(transaction['date'], '%Y-%m-%d')
    transaction_contact = transaction.get('contact', '')
    
    best_match = None
    best_score = 0
    
    for att in attachments:
        att_data = att.get('data', att)
        score = _calculate_match_score(
            transaction_amount,
            transaction_date,
            transaction_contact,
            att_data,
            )
        
        # Determine minimum required score
        # If contact exists: need all 3 signals (amount + date + name)
        # If no contact: accept amount + date
        min_score = \
            MIN_SCORE_WITHOUT_CONTACT \
            if not transaction_contact \
            else MIN_SCORE_WITH_CONTACT
        
        if score < min_score:
            continue
        
        # Update best match (prefer higher score, then lower ID for determinism)
        if score > best_score:
            best_score = score
            best_match = att
        elif score == best_score and best_match and att['id'] < best_match['id']:
            best_match = att
    
    return best_match


def find_transaction(
    attachment: Attachment,
    transactions: list[Transaction],
) -> Transaction | None:
    """Find the best matching transaction for a given attachment.
    
    Matching strategy:
    1. Reference number match (highest priority, always 1:1)
    2. Amount + Date + Name combination (requires all 3 if contact exists)
    
    Args:
        attachment: Attachment dictionary with nested 'data' field
        transactions: List of transaction dictionaries
        
    Returns:
        Best matching transaction or None if no confident match found
    """
    att_data = attachment.get('data', attachment)
    
    # Priority 1: Reference number match (1:1 mapping)
    att_ref = normalize_reference(att_data.get('reference'))
    if att_ref:
        for transaction in transactions:
            transaction_ref = normalize_reference(transaction.get('reference'))
            if transaction_ref == att_ref:
                return transaction
    
    # Priority 2: Amount + Date + Name matching
    att_amount = float(att_data['total_amount'])
    att_date = (
        datetime.strptime(att_data['due_date'], '%Y-%m-%d')
        if att_data.get('due_date')
        else None
    )
    att_names = [
        name
        for name in [
            att_data.get('issuer'),
            att_data.get('recipient'),
            att_data.get('supplier'),
        ]
        if name
    ]
    
    best_match = None
    best_score = 0
    
    for transaction in transactions:
        score = 0
        
        # Amount must match (within tolerance)
        transaction_amount = abs(float(transaction['amount']))
        if abs(transaction_amount - att_amount) >= AMOUNT_TOLERANCE:
            continue
        score += SCORE_AMOUNT
        
        # Date within tolerance window
        if att_date:
            transaction_date = \
                datetime.strptime(transaction['date'], '%Y-%m-%d')
            days_diff = abs((transaction_date - att_date).days)
            if days_diff <= DATE_TOLERANCE_DAYS:
                score += SCORE_DATE
        
        # Name match
        transaction_contact = transaction.get('contact', '')
        if any(names_match(
            transaction_contact,
            name
            ) for name in att_names):
            score += SCORE_NAME
        
        # Determine minimum required score
        min_score = MIN_SCORE_WITHOUT_CONTACT \
            if not transaction_contact \
            else MIN_SCORE_WITH_CONTACT
        
        if score < min_score:
            continue
        
        # Update best match (prefer higher score)
        if score > best_score:
            best_score = score
            best_match = transaction
        elif score == best_score \
                and best_match \
                and transaction['id'] < best_match['id']:
            best_match = transaction
    
    return best_match