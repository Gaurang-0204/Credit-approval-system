# loans/services/eligibility_service.py
from decimal import Decimal
from datetime import date
from loans.models import Customer, Loan, LoanApplication, CreditScore

def calculate_credit_score(customer: Customer) -> int:
    """
    Simplified credit score calculation (0–100).
    Components:
    - Past loans paid on time
    - Number of loans taken
    - Loan activity in current year
    - Loan approved volume
    """

    loans = customer.loans.all()
    if not loans.exists():
        return 50  # neutral score for no history

    score = 0

    # i. Past loans paid on time (max 30 points)
    on_time_ratio = sum(1 for loan in loans if loan.emis_paid_on_time > 0) / len(loans)
    score += int(on_time_ratio * 30)

    # ii. Number of loans taken (max 20 points)
    score += min(len(loans) * 5, 20)

    # iii. Loan activity in current year (max 20 points)
    current_year = date.today().year
    loans_this_year = [loan for loan in loans if loan.start_date.year == current_year]
    score += min(len(loans_this_year) * 5, 20)

    # iv. Loan approved volume (max 20 points)
    total_volume = sum(float(loan.loan_amount) for loan in loans)
    score += min(int(total_volume / 100000), 20)  # 1 point per lakh

    # v. Cap score to 100
    return min(score, 100)


def evaluate_loan(customer: Customer, loan_amount: Decimal, interest_rate: Decimal, tenure: int):
    """
    Apply business rules to check loan eligibility
    """
    credit_score = calculate_credit_score(customer)

    # Rule: If sum of current loans > approved limit → score = 0
    if customer.get_current_loans_sum() > customer.approved_limit:
        credit_score = 0

    # EMI calculation
    annual_rate = float(interest_rate)
    n = tenure
    r = annual_rate / (12 * 100)
    principal = float(loan_amount)

    if r == 0:
        emi = Decimal(str(principal / n))
    else:
        emi = Decimal(str((principal * r * (1 + r) ** n) / ((1 + r) ** n - 1))).quantize(Decimal("0.01"))

    # Rule: if EMIs > 50% of salary → reject
    if (customer.get_current_emis_sum() + emi) > (Decimal("0.5") * customer.monthly_salary):
        return False, credit_score, interest_rate, None, emi

    # Rule: approve/reject based on score
    approved = True
    corrected_interest_rate = interest_rate

    if credit_score > 50:
        approved = True
    elif 30 < credit_score <= 50:
        if interest_rate <= Decimal("12.0"):
            corrected_interest_rate = Decimal("12.1")  # minimum allowed
    elif 10 < credit_score <= 30:
        if interest_rate <= Decimal("16.0"):
            corrected_interest_rate = Decimal("16.1")
    else:
        approved = False

    return approved, credit_score, interest_rate, corrected_interest_rate, emi
