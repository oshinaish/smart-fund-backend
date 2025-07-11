# app.py

from flask import Flask, request, jsonify
from flask_cors import CORS
import math

app = Flask(__name__)
CORS(app) # Enable CORS for all routes

# --- Global Constants (from your frontend code) ---
FIXED_LOAN_INTEREST_RATE = 8  # 8% Annual
FIXED_LOAN_TENURE_YEARS = 30  # 30 Years
RISK_APPETITE_RETURNS = {
    "low": 6,
    "moderate": 9,
    "high": 12
}

# --- Financial Calculation Functions (Translated from JavaScript) ---

def calculate_emi(principal, annual_rate, tenure_years):
    if principal <= 0 or tenure_years <= 0:
        return 0
    monthly_rate = (annual_rate / 100) / 12
    num_payments = tenure_years * 12
    if monthly_rate == 0:
        return principal / num_payments
    return principal * monthly_rate / (1 - math.pow(1 + monthly_rate, -num_payments))

def calculate_total_interest(principal, emi, tenure_years):
    num_payments = tenure_years * 12
    return (emi * num_payments) - principal

def calculate_sip_future_value(monthly_investment, annual_rate, tenure_years):
    if monthly_investment <= 0 or tenure_years <= 0:
        return 0
    monthly_rate = (annual_rate / 100) / 12
    num_months = tenure_years * 12
    if monthly_rate == 0:
        return monthly_investment * num_months
    # Formula for Future Value of an Annuity Due (investment at start of month)
    return monthly_investment * (math.pow(1 + monthly_rate, num_months) - 1) / monthly_rate * (1 + monthly_rate)

def calculate_required_sip(future_value, annual_rate, tenure_years):
    if future_value <= 0 or tenure_years <= 0:
        return 0
    monthly_rate = (annual_rate / 100) / 12
    num_months = tenure_years * 12
    if monthly_rate == 0:
        return future_value / num_months
    return future_value * monthly_rate / ((math.pow(1 + monthly_rate, num_months) - 1) * (1 + monthly_rate))

def calculate_remaining_loan_balance(principal, annual_rate, original_tenure_years, payments_made_years):
    if principal <= 0 or original_tenure_years <= 0 or payments_made_years < 0 or payments_made_years > original_tenure_years:
        return principal
    
    if payments_made_years == 0:
        return principal # No payments made yet

    monthly_rate = (annual_rate / 100) / 12
    total_payments = original_tenure_years * 12
    payments_made = payments_made_years * 12

    if monthly_rate == 0:
        return principal * (1 - (payments_made / total_payments))

    emi = calculate_emi(principal, annual_rate, original_tenure_years)
    remaining_balance = principal * math.pow(1 + monthly_rate, payments_made) - emi * (math.pow(1 + monthly_rate, payments_made) - 1) / monthly_rate
    return max(0, remaining_balance) # Ensure balance doesn't go negative


# --- API Endpoints ---

@app.route('/api/calculate-net-zero-interest', methods=['POST'])
def calculate_net_zero_interest():
    data = request.get_json()
    loan_amount = data.get('loanAmount')
    monthly_budget = data.get('monthlyBudget')
    risk_appetite = data.get('riskAppetite')

    expected_return_rate = RISK_APPETITE_RETURNS.get(risk_appetite)

    standard_emi = calculate_emi(loan_amount, FIXED_LOAN_INTEREST_RATE, FIXED_LOAN_TENURE_YEARS)
    total_loan_interest_payable = calculate_total_interest(loan_amount, standard_emi, FIXED_LOAN_TENURE_YEARS)
    required_monthly_investment = calculate_required_sip(total_loan_interest_payable, expected_return_rate, FIXED_LOAN_TENURE_YEARS)
    available_for_investment = monthly_budget - standard_emi

    if required_monthly_investment > available_for_investment:
        response = {
            "status": "not_achievable",
            "monthlyEMI": standard_emi,
            "monthlyInvestment": available_for_investment if available_for_investment > 0 else 0,
            "totalLoanInterestPayable": total_loan_interest_payable,
            "estimatedInvestmentFutureValue": calculate_sip_future_value(available_for_investment if available_for_investment > 0 else 0, expected_return_rate, FIXED_LOAN_TENURE_YEARS),
            "guidanceMessage": f"Cannot achieve Net Zero interest with current budget. You need to invest {required_monthly_investment:.0f} monthly, but only {available_for_investment:.0f} is available after EMI.",
            "chartData": {"loanInterest": total_loan_interest_payable, "investmentGain": calculate_sip_future_value(available_for_investment if available_for_investment > 0 else 0, expected_return_rate, FIXED_LOAN_TENURE_YEARS)},
            "recommendation": "Increase budget or reduce loan to achieve this goal."
        }
    else:
        response = {
            "status": "success",
            "monthlyEMI": standard_emi,
            "monthlyInvestment": required_monthly_investment,
            "totalLoanInterestPayable": total_loan_interest_payable,
            "estimatedInvestmentFutureValue": total_loan_interest_payable, # By definition, we hit the target
            "guidanceMessage": f"To achieve Net Zero interest, allocate {required_monthly_investment:.0f} monthly to investments.",
            "chartData": {"loanInterest": total_loan_interest_payable, "investmentGain": total_loan_interest_payable},
            "recommendation": "Achievable. Your investment strategy is aligned to offset loan interest."
        }
    return jsonify(response)

@app.route('/api/calculate-min-time-net-zero', methods=['POST'])
def calculate_min_time_net_zero():
    data = request.get_json()
    loan_amount = data.get('loanAmount')
    monthly_budget = data.get('monthlyBudget')
    risk_appetite = data.get('riskAppetite')

    expected_return_rate = RISK_APPETITE_RETURNS.get(risk_appetite)

    min_time_years = -1
    best_result = {}

    for tenure in range(1, FIXED_LOAN_TENURE_YEARS + 1):
        current_emi = calculate_emi(loan_amount, FIXED_LOAN_INTEREST_RATE, tenure)
        current_total_interest = calculate_total_interest(loan_amount, current_emi, tenure)
        current_available_investment = monthly_budget - current_emi

        if current_available_investment <= 0:
            continue # Not enough budget for investment

        current_investment_fv = calculate_sip_future_value(current_available_investment, expected_return_rate, tenure)

        if current_investment_fv >= current_total_interest:
            min_time_years = tenure
            best_result = {
                "monthlyEMI": current_emi,
                "monthlyInvestment": current_available_investment,
                "totalLoanInterestPayable": current_total_interest,
                "estimatedInvestmentFutureValue": current_investment_fv,
            }
            break # Found the minimum time

    if min_time_years != -1:
        response = {
            "status": "success",
            "minTimeYears": min_time_years,
            "monthlyEMI": best_result["monthlyEMI"],
            "monthlyInvestment": best_result["monthlyInvestment"],
            "totalLoanInterestPayable": best_result["totalLoanInterestPayable"],
            "estimatedInvestmentFutureValue": best_result["estimatedInvestmentFutureValue"],
            "guidanceMessage": f"Achieve Net Zero interest in {min_time_years} years by allocating {best_result['monthlyInvestment']:.0f} monthly.",
            "chartData": {"loanInterest": best_result["totalLoanInterestPayable"], "investmentGain": best_result["estimatedInvestmentFutureValue"]},
            "recommendation": "Optimal tenure found for offsetting interest."
        }
    else:
        # If not achievable within max tenure, calculate for max tenure to show current state
        standard_emi = calculate_emi(loan_amount, FIXED_LOAN_INTEREST_RATE, FIXED_LOAN_TENURE_YEARS)
        available_for_investment = monthly_budget - standard_emi
        investment_fv_at_max_tenure = calculate_sip_future_value(available_for_investment if available_for_investment > 0 else 0, expected_return_rate, FIXED_LOAN_TENURE_YEARS)
        total_interest_at_max_tenure = calculate_total_interest(loan_amount, standard_emi, FIXED_LOAN_TENURE_YEARS)

        response = {
            "status": "not_achievable",
            "minTimeYears": FIXED_LOAN_TENURE_YEARS, # Indicates max tenure reached
            "monthlyEMI": standard_emi,
            "monthlyInvestment": available_for_investment if available_for_investment > 0 else 0,
            "totalLoanInterestPayable": total_interest_at_max_tenure,
            "estimatedInvestmentFutureValue": investment_fv_at_max_tenure,
            "guidanceMessage": f"Cannot achieve Net Zero interest within {FIXED_LOAN_TENURE_YEARS} years with current budget and investment strategy.",
            "chartData": {"loanInterest": total_interest_at_max_tenure, "investmentGain": investment_fv_at_max_tenure},
            "recommendation": "Increase budget, reduce loan, or increase risk appetite."
        }
    return jsonify(response)

@app.route('/api/calculate-max-growth', methods=['POST'])
def calculate_max_growth():
    data = request.get_json()
    loan_amount = data.get('loanAmount')
    monthly_budget = data.get('monthlyBudget')
    risk_appetite = data.get('riskAppetite')
    optimization_period_years = data.get('optimizationPeriodYears')

    expected_return_rate = RISK_APPETITE_RETURNS.get(risk_appetite)

    standard_emi = calculate_emi(loan_amount, FIXED_LOAN_INTEREST_RATE, FIXED_LOAN_TENURE_YEARS)
    monthly_investment = monthly_budget - standard_emi

    if monthly_investment <= 0:
        response = {
            "status": "not_achievable",
            "monthlyEMI": standard_emi,
            "monthlyInvestment": 0,
            "optimizationPeriodYears": optimization_period_years,
            "estimatedInvestmentFutureValue": 0,
            "remainingLoanBalance": calculate_remaining_loan_balance(loan_amount, FIXED_LOAN_INTEREST_RATE, FIXED_LOAN_TENURE_YEARS, optimization_period_years),
            "netWealthAtPeriodEnd": 0,
            "guidanceMessage": "No funds available for investment to maximize growth.",
            "chartData": {"investmentFV": 0, "remainingLoan": calculate_remaining_loan_balance(loan_amount, FIXED_LOAN_INTEREST_RATE, FIXED_LOAN_TENURE_YEARS, optimization_period_years)},
            "recommendation": "Increase budget or reduce loan to enable investment."
        }
    else:
        investment_fv = calculate_sip_future_value(monthly_investment, expected_return_rate, optimization_period_years)
        remaining_loan = calculate_remaining_loan_balance(loan_amount, FIXED_LOAN_INTEREST_RATE, FIXED_LOAN_TENURE_YEARS, optimization_period_years)
        net_wealth = investment_fv - remaining_loan

        response = {
            "status": "success",
            "monthlyEMI": standard_emi,
            "monthlyInvestment": monthly_investment,
            "optimizationPeriodYears": optimization_period_years,
            "estimatedInvestmentFutureValue": investment_fv,
            "remainingLoanBalance": remaining_loan,
            "netWealthAtPeriodEnd": net_wealth,
            "guidanceMessage": f"Maximize growth: Your estimated Net Wealth in {optimization_period_years} years is {net_wealth:.0f}.",
            "chartData": {"investmentFV": investment_fv, "remainingLoan": remaining_loan},
            "recommendation": "Focus on wealth accumulation while managing loan."
        }
    return jsonify(response)


if __name__ == '__main__':
    app.run(debug=True, port=5000) # Run on port 5000, debug=True for development
