import argparse
import inspect
import functools
import numpy as np

import matplotlib.pyplot as plt
from matplotlib.dates import date2num

import sys


from datetime import datetime

### Helper functions
def fn_name_comps():
    '''returns all computation functions to choose from'''
    return [name[5:] for name, object in inspect.getmembers(sys.modules['__main__']) if inspect.isfunction(object) and name.startswith('comp_')]

def fn_name_parser():
    '''returns all parser functions for computations'''
    return [f'parser_{x}' for x in fn_name_comps()]

def fn_load(name):
    '''loads given function in main invocation module'''
    return getattr(sys.modules['__main__'], name)


def calc_annuity(amount, interest, duration):
    return ((interest/12) / (1-((1+interest/12) ** -duration))) * amount

def calc_base(amount, interest, type, duration):
    '''Returns the debt payments to be paid each month'''
    if type == 'linear':
        return np.full(duration, amount / duration) # amount to be paid each month for the base loan (no interest)
    elif type == 'annuity': # ref: https://www.homefinance.nl/hypotheek/berekenen/annuiteit/
        annuity = calc_annuity(amount, interest, duration)
        return np.full(duration, annuity) - calc_payment_interest(amount, interest, type, duration)

def calc_interest(debt, interest):
    '''Returns the interest to be paid each month'''
    return debt*interest/12 # simply put: each month you pay the open debt * interest / 12

# def calc_payment_interest(amount, interest, type, duration):
#     if type == 'linear' or type == 'annuity':
#         factor = amount / duration
#         return (np.full(duration, amount) - np.arange(duration)*factor)*interest/12 # simply put: each month you pay the open debt * interest/12

def calc_debt(debt_payments):
    '''Returns the remaining debt at each month'''
    return np.full(len(debt_payments), np.sum(debt_payments) - np.cumsum(debt_payments))
    
def calc_shorten_duration(base, amount):
    total = 0
    idx = 0
    rev_base = base[::-1]
    while total < amount and idx < len(base):
        total += rev_base[idx]
        idx += 1
    if total >= amount:
        ans =  base[:-idx] if total == amount else np.concatenate((base[:-idx], [round(total-amount, 2)])) # TODO: introduce more precise floating points
        return ans
    raise RuntimeError('Amount paid is too large! The entire loan will be paid off with this amount.')

### computations (with their respective parser functions)
def parser_basic(subparsers):
    return subparsers.add_parser('basic')

def comp_basic(args):
    # Compute basic loan statistics
    base = calc_base(args.loan, args.interest, args.type, args.duration)
    debt = calc_debt(base)
    interest = calc_interest(debt, args.interest)
    combined = base + interest
    print(f'total: {np.sum(combined)}')
    if args.visual:
        x = np.arange(args.start, args.duration, dtype='datetime64[M]')
        x = date2num(x)

        fig, ax = plt.subplots()
        ax.plot(x, debt, label='debt', marker='.')
        # ax.plot(x, early_debt, label='debt (w/ early payment)', marker='.')

        w = 15.5 # this is the bar width, expressed in days
        ax.bar(x, np.cumsum(base), label='debt paid', width=w)
        ax.bar(x, np.cumsum(interest), bottom=np.cumsum(base), label='interest paid', width=w)

        # ax.bar(x+w, np.cumsum(early_base), label='debt paid (early)', width=w)
        # ax.bar(x+w, np.cumsum(early_interest), bottom=np.cumsum(early_base), label='interest paid (early)', width=w)

        ax.xaxis_date()
        plt.ylabel('euros')

        plt.legend()
        plt.title('Payment accumulation over the years (bruto)')
        plt.show()

        # second graph starts here
        fig, ax = plt.subplots()
        # ax.plot(x, debt, label='debt', marker='.')
        # ax.plot(x, early_debt, label='debt (w/ early payment)', marker='.')

        w = 15.5 # this is the bar width, expressed in days
        ax.bar(x, interest, label='monthly interest paid', width=w)

        # ax.bar(x+w, np.cumsum(early_base), label='debt paid (early)', width=w)
        # ax.bar(x+w, np.cumsum(early_interest), bottom=np.cumsum(early_base), label='interest paid (early)', width=w)

        ax.xaxis_date()
        plt.ylabel('euros')

        plt.legend()
        plt.title('Payment accumulation over the years')
        plt.show()


def calc_income_tax(income):
    bracket_amounts =  [75_624, float("inf")]
    bracket_percentages = [0.3748, 0.4950] # the actual income percentages shift a bit over time, but this should be accurate enough
    return income * bracket_percentages[0] if income < bracket_amounts[0] else (bracket_amounts[0] * bracket_percentages[0]) + ((income-bracket_amounts[0]) * bracket_percentages[1])
    
def calc_hypotheekrente_aftrek(interest: np.array, incomes: np.array, house_worths: np.array, max_deduction_rates: np.array) -> float:
    # compute hyptoheekrente aftrek

    calcs = []
    for income, interest_paid, eigenwoning_forfait, max_deduction_rate in zip(incomes, interest, house_worths*0.0035, max_deduction_rates): # iterates years (i.e. yearly income, yearly interest paid)
        tax_before = calc_income_tax(income)
        tax_after = calc_income_tax(max(0, income - interest_paid))
        savings = (tax_before - tax_after) - eigenwoning_forfait * max_deduction_rate
        calcs.append(min(savings, interest_paid * max_deduction_rate))
    return np.array(calcs)
    # return np.array([min(calc_income_tax(income) - calc_income_tax(max(0, income - interest_paid)), interest_paid * max_deduction_rate) for income, interest_paid in zip(incomes, calc_interest(debt, interest))])

def parser_hypotheekrente_aftrek(subparsers):
    sub = subparsers.add_parser('hypotheekrente_aftrek')
    sub.add_argument('--income', type=float, required=True, help='Sum to be paid early')
    sub.add_argument('--house-worth', type=float, required=True, help='WOZ waarde (worth of a house according to tax people)')
    sub.add_argument('--emulate-house-increase', type=float, help='Emulates house price increases for realism. Provide as "0.02" for 2% increase year after year.')
    sub.add_argument('--emulate-income', type=float, help='Emulates income increase for realism. Provide as "0.02" for 2% income increase year after year.')
    sub.add_argument('--extra-builddown-start', type=lambda s: datetime.strptime(s, '%Y'), help='Emulates yearly-linear deduction removal, this sets the start. Provide a year, like "2040".')
    sub.add_argument('--extra-builddown-end', type=lambda s: datetime.strptime(s, '%Y'), help='Emulates yearly-linear deduction removal, this sets the end. Provide a year, like "2040".')
    return sub

def comp_hypotheekrente_aftrek(args):
    base = calc_base(args.loan, args.interest, args.type, args.duration)
    debt = calc_debt(base)
    interest = calc_interest(debt, args.interest).reshape(-1, 12).sum(axis=1)
    # incomes over time (yearly basis)
    incomes = np.full(args.duration//12, args.income) if not args.emulate_income else args.income * ((1.0+args.emulate_income)**np.array(args.duration // 12))
    house_worths = np.full(args.duration//12, args.house_worth) if not args.emulate_house_increase else args.house_worth * ((1.0+args.emulate_house_increase)**np.array(args.duration // 12))
    max_deduction_rates = np.full(len(interest), 0.3748)

    if args.start.year < 2024:
        print('minor inaccuracies: before 2024, hypotheekrenteaftrek was a lot more than it is now. So the results here are more of a lower limit to you.')

    tax_gains = calc_hypotheekrente_aftrek(interest, incomes, house_worths, max_deduction_rates)
    print(f'Total gains: {np.sum(tax_gains)}')

    if args.extra_builddown_start:
        assert args.extra_builddown_end != None
        year_start_idx = (args.extra_builddown_start.year - args.start.year)
        year_end_idx = (args.extra_builddown_end.year - args.start.year)
        max_deduction_rates = np.array([0.3748 for x in range (year_start_idx)] + [0.3748 - (0.3748/(year_end_idx - year_start_idx)*(x+1)) for x in range(year_end_idx-year_start_idx)] + [0 for x in range((args.duration//12) - year_end_idx)])
        assert len(max_deduction_rates) == len(incomes)
        tax_gains_with_removal = calc_hypotheekrente_aftrek(interest, incomes, house_worths, max_deduction_rates)
        delta = np.sum(tax_gains) - np.sum(tax_gains_with_removal)
        print(f'Total gains: {np.sum(tax_gains_with_removal)} (with the builddown)')
        print(f'Delta is {delta} in total, or {delta/(args.duration/12)} per year, or {delta/args.duration} every month for {args.duration} months')


    if args.visual:
        x = np.arange(args.start, args.duration // 12, dtype='datetime64[Y]')
        x = date2num(x)

        fig, ax = plt.subplots()
        w = 15.5 # this is the bar width, expressed in days
        ax.plot(x, tax_gains / 12, label='hypotheekrente aftrek gains', marker='.')
        if args.extra_builddown_start:
            ax.plot(x, tax_gains_with_removal / 12, label='hypotheekrente aftrek gains (with fast removal)', marker='.')

        ax.xaxis_date()
        plt.ylabel('euros')

        plt.legend()
        plt.title('Deduction gains every month')
        plt.show()

        fig, ax = plt.subplots()
        w = 15.5 # this is the bar width, expressed in days
        ax.plot(x, np.cumsum(tax_gains), label='hypotheekrente aftrek gains', marker='.')
        if args.extra_builddown_start:
            ax.plot(x, np.cumsum(tax_gains_with_removal), label='hypotheekrente aftrek gains (with fast removal)', marker='.')

        ax.xaxis_date()
        plt.ylabel('euros')

        plt.legend()
        plt.title('Deduction gain sum totals')
        plt.show()


def parser_early_payment(subparsers):
    sub = subparsers.add_parser('early_payment')
    sub.add_argument('--amount', type=float, required=True, help='Sum to be paid early')
    # TODO: Maybe add support for multiple occurences
    sub.add_argument('--date', type=lambda s: datetime.strptime(s, '%Y-%m-%d'), required=True, help='Date at which sum is paid early (as yyyy-mm-dd).')
    sub.add_argument('--decision', choices=['shorten', 'keep'], required=True, help='Decision on what happens after early payment: Shorten the duration and keep paying as-is now (shorten) OR keep the duration as-is and recalculate monthly payments (keep).')
    return sub

def comp_early_payment(args):
    month_idx = (args.date.year - args.start.year)*12 + args.date.month - args.start.month # month where extra payment happened

    base = calc_base(args.loan, args.interest, args.type, args.duration)
    debt = calc_debt(base)
    interest = calc_interest(debt, args.interest)
    combined = base + interest
    if debt[month_idx] < args.amount:
        print(f'error: You only have {debt[month_idx]} to pay off at given date.')
        return

    print('If not paying early:')
    print(f'total: {np.sum(combined)}')
    print()

    early_base = np.copy(base)
    early_base[month_idx] += args.amount
    if args.decision == 'keep':
        early_base[month_idx+1:] = calc_base(args.loan-np.sum(early_base[:month_idx+1]), args.interest, args.type, args.duration-month_idx-1)
    elif args.decision == 'shorten':
        early_base = calc_shorten_duration(early_base, args.amount)
    early_debt = calc_debt(early_base)
    early_interest = calc_interest(early_debt, args.interest)
    early_combined = early_base + early_interest

    print('If paying early:')
    early_sum = np.sum(early_combined)
    norm_sum = np.sum(combined)
    delta_sum = norm_sum - early_sum # computes what the user saves by paying early
    months = (len(combined) - month_idx) # the remaining months (where the early payment happened)
    annual_percentage_gain = (((args.amount+delta_sum)/args.amount)**(1/(months/12)) - 1) * 100 # computes how much the user saves per year as a percentage 
    
    print(f'total: {early_sum}')

    if args.decision == 'shorten':
        months_saved = len(combined) - len(early_combined)
        annual_percentage_gain = (((args.amount+delta_sum)/args.amount)**(1/(months/12)) - 1) * 100
        print(f'{args.decision}: By paying {args.amount} early, you save {months_saved} months ({months_saved/12} years) of payments.')

    print(f'general: By paying {args.amount} early, you save {delta_sum} (i.e. {delta_sum * 100 / args.amount}%) over {months} months, ({months/12} years).')
    print(f'general: This provides you {annual_percentage_gain}% yoy as "interest"')

    if args.visual:
        if args.decision == 'shorten': # the early array is shortened. Numpy doesn't like it
            early_base = np.concatenate((early_base, np.full(len(base)-len(early_base), 0)))
            early_debt = np.concatenate((early_debt, np.full(len(debt)-len(early_debt), 0)))
            early_interest = np.concatenate((early_interest, np.full(len(interest)-len(early_interest), 0)))
        # assert np.sum(base) == np.sum(early_base) # TODO; this assertion fails due to a very small offset due to floating points
        assert len(base) == len(early_base)
        assert len(interest) == len(early_interest)
        assert len(early_base) == len(early_interest)
        x = np.arange(args.start, args.duration, dtype='datetime64[M]')
        x = date2num(x)

        fig, ax = plt.subplots()
        ax.plot(x, debt, label='debt', marker='.')
        ax.plot(x, early_debt, label='debt (w/ early payment)', marker='.')

        w = 15.5 # this is the bar width, expressed in days
        ax.bar(x-w, np.cumsum(base), label='debt paid', width=w)
        ax.bar(x-w, np.cumsum(interest), bottom=np.cumsum(base), label='interest paid', width=w)

        ax.bar(x, np.cumsum(early_base), label='debt paid (early)', width=w)
        ax.bar(x, np.cumsum(early_interest), bottom=np.cumsum(early_base), label='interest paid (early)', width=w)

        ax.xaxis_date()
        plt.ylabel('euros')

        plt.legend()
        plt.show()

    # TODO: calc net trouble

### Main program section
def main():
    # Simple program to calculate normalized cost for power & gas grid connections.
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(help='type of computation to execute', dest='computation')

    parser.add_argument('--loan', type=float, required=True, help='Total loan sum at given date.')
    parser.add_argument('--interest', type=float, required=True, help='Interest in percents. E.g. pass `3.5` when the interest rate is 3.5 percent.')
    parser.add_argument('--type', required=True, choices=['linear', 'annuity'], help='Type of mortgage.')
    parser.add_argument('--start', type=lambda s: datetime.strptime(s, '%Y-%m-%d'), required=True, help='Date at which the mortgage started (as yyyy-mm-dd).')
    parser.add_argument('--duration', type=int, default = 30*12, help='Amount of months for the loan, i.e. in how many months the mortgage should be paid back in full.')
    parser.add_argument('--visual', action='store_true', help='Show the graphs!')

    subs = [fn_load(fn)(subparsers) for fn in fn_name_parser()]
        
    args = parser.parse_args()
    args.interest /= 100


    if args.computation:
        fn_load(f'comp_{args.computation}')(args)
    else:
        print(f'No specific computation requested. Options: "{fn_name_comps()}"')

if __name__ == '__main__':
    main()
