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
    

### computations (with their respective parser functions)
def parser_basic(subparsers):
    return subparsers.add_parser('basic')

def comp_basic(args):
    base = calc_base(args.loan, args.interest, args.type, args.duration)
    debt = calc_debt(base)
    interest = calc_interest(debt, args.interest)
    combined = base + interest
    print(f'total: {np.sum(combined)}')


def parser_early_payment(subparsers):
    sub = subparsers.add_parser('early_payment')
    sub.add_argument('--amount', type=float, required=True, help='Sum to be paid early')
    sub.add_argument('--date', type=lambda s: datetime.strptime(s, '%Y-%m-%d'), required=True, help='Date at which sum is paid early (as yyyy-mm-dd).')
    sub.add_argument('--decision', choices=['shorten', 'keep'], required=True, help='Decision on what happens after early payment: Shorten the duration and keep paying as-is now (shorten) OR keep the duration as-is and recalculate monthly payments (keep).')
    return sub

def comp_early_payment(args):
    # TODO: Maybe add support for multiple occurences
    base = calc_base(args.loan, args.interest, args.type, args.duration)
    debt = calc_debt(base)
    interest = calc_interest(debt, args.interest)
    combined = base + interest

    print('If not paying early:')
    print(f'total: {np.sum(combined)}')
    print()

    month_idx = (args.date.year - args.start.year)*12 + args.date.month - args.start.month # month where extra payment happened
    early_base = np.copy(base)
    early_base[month_idx] += args.amount
    if args.decision == 'keep':
        early_base[month_idx+1:] = calc_base(args.loan-np.sum(early_base[:month_idx+1]), args.interest, args.type, args.duration-month_idx-1)
    elif args.decision == 'shorten':
        pass
        # TODO: shorten calculation
    early_debt = calc_debt(early_base)
    early_interest = calc_interest(early_debt, args.interest)
    early_combined = early_base + early_interest

    print('If paying early:')
    print(f'total: {np.sum(early_combined)}')

    if args.visual:
        x = np.arange(args.start, args.duration, dtype='datetime64[M]')
        x = date2num(x)

        fig, ax = plt.subplots()
        ax.plot(x, debt, label='debt', marker='.')
        ax.plot(x, early_debt, label='debt (w/ early payment)', marker='.')

        w = 15.5 # this is the bar width, expressed in days
        ax.bar(x-w, np.cumsum(base), label='debt paid', width=w)
        ax.bar(x-w, np.cumsum(interest), bottom=np.cumsum(base), label='interest', width=w)

        ax.bar(x, np.cumsum(early_base), label='debt paid (early)', width=w)
        ax.bar(x, np.cumsum(early_interest), bottom=np.cumsum(early_base), label='interest (early)', width=w)

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
        print('No specific computation requested')

if __name__ == '__main__':
    main()
