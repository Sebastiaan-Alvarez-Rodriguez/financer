import argparse
import inspect
import functools
import numpy as np
import sys


from datetime import datetime

def calc_annuity(amount, interest, duration):
    return ((interest/12) / (1-((1+interest/12) ** -duration))) * amount

def calc_payment_base(amount, interest, type, duration):
    if type == 'linear':
        factor = amount / duration
        return np.full(duration, factor) # amount to be paid each month for the base loan (no interest)
    elif type == 'annuity': # ref: https://www.homefinance.nl/hypotheek/berekenen/annuiteit/
        annuity = calc_annuity(amount, interest, duration)
        return np.full(duration, annuity) - calc_payment_interest(amount, interest, type, duration)

def calc_payment_interest(amount, interest, type, duration):
    if type == 'linear' or type == 'annuity':
        factor = amount / duration
        return (np.full(duration, amount) - np.arange(duration)*factor)*interest/12 # simply put: each month you pay the open debt * interest/12

def comp_early_payment(args, base, interest):
    # TODO: pass an extra arg to specify how much money at what date is paid early. Maybe add support for multiple occurences
    pass

def main():
    computation_options = [name[5:] for name, object in inspect.getmembers(sys.modules[__name__]) if inspect.isfunction(object) and name.startswith('comp_')]

    # Simple program to calculate normalized cost for power & gas grid connections.
    parser = argparse.ArgumentParser()
    parser.add_argument('--loan', type=float, required=True, help='Total loan sum at given date.')
    parser.add_argument('--interest', type=float, required=True, help='Interest in percents. E.g. pass `3.5` when the interest rate is 3.5%.')
    parser.add_argument('--type', required=True, choices=['linear', 'annuity'], help='Type of mortgage.')
    parser.add_argument('--date', type=lambda s: datetime.strptime(s, '%Y-%m-%d'), required=True, help='Date at which the mortgage started (as yyyy-mm-dd).')
    parser.add_argument('--duration', type=int, default = 30*12, help='Amount of months for the loan, i.e. in how many months the mortgage should be paid back in full.')
    parser.add_argument('--visual', action='store_true', help='Show the graphs!')
    parser.add_argument('--computation', type=str, choices=computation_options, help=f'Computation to perform.')

    args = parser.parse_args()
    args.interest /= 100

    base = calc_payment_base(args.loan, args.interest, args.type, args.duration)
    interest = calc_payment_interest(args.loan, args.interest, args.type, args.duration)
    combined = base + interest

    if args.computation:
        func = getattr(sys.modules['__main__'], f'comp_{args.computation}')
    else:
        print('No specific computation requested')
        print(combined)
        print()
        print()
        print(f'total: {np.sum(combined)}')

if __name__ == '__main__':
    main()
