#!/usr/bin/env python3
"""
Generate mock reactions data for channel_messages CSV files.

This script takes an input CSV containing channel_messages data (without reactions)
and outputs a new CSV with a generated 'reactions' column containing realistic mock data.
"""

import argparse
import json
import random
from pathlib import Path

import pandas as pd


REACTION_NAMES = [
    'approved',
    'merged',
    'raised_hands',
    'pray',
    'laugh',
    'ty',
    'this',
    'point_up',
    'white_check_mark'
]

MOCK_SLACK_USER_IDS = [
    'U1FM88J9J',
    'UNC2V4ZD7',
    'U7W96XW2A',
    'US3QTX4Z1',
    'UQY0NPYWN',
    'UR257U86O',
    'UG6UG9470',
    'U0KG42Q0P',
    'UEA8H90WN',
    'UNNH8IW78',
    'U3GY5K9EQ',
    'UL9VWQ9S2',
    'UORS33I12',
    'U8S28EIM6',
    'UWL5JX23M',
    'UV77JEL7Q',
    'U2M260029',
    'UFF1HYHJ2',
    'UDC0ZA535',
    'UB81I8027',
    'U3HY0BS3W',
    'UL92954KA',
    'UZ5125Y28',
    'U168N7Y9G',
    'UE83A3954',
    'UP9T7VJBF',
    'UK839UQ5R',
    'UCL2RJ89X',
    'UFUV7GPHM',
    'UNVWFC5Q1',
    'UY640917T',
    'UQSF747QR',
    'U34AX16M0',
    'UWBXBIUB7',
    'U2QXC4ZNG',
    'UN979RN92',
    'UH749DC04',
    'UL2989703',
    'U4095YWYD',
    'U24SJD0U3',
    'U7ZP08017',
    'U0GBC0N90',
    'UU6K92DUR',
    'UNY6WDI60',
    'UJ65P6F44',
    'U3TE14ET2',
    'U96N45CL2',
    'UK4V3ON2O',
    'UKA77QAYY',
    'U81OT695K',
    'UPT27H737',
    'UOBK5OFZ0',
    'U0EIW7DOX',
    'UZ271WU40',
    'UYVM94HE1',
    'UEZMYV74R',
    'UYEP6YY91',
    'U9E255NN9',
    'ULRS0HVJ3',
    'U378U76S4',
    'UK756E555',
    'U6P582A60',
    'UL96240J4',
    'UU95TZPYP',
    'U306GEBY8',
    'U549234TU',
    'UIX8TSI0Y',
    'UE0WA7608',
    'U9YFOYM78',
    'UZ90K3JDW',
    'U5V38TNV1',
    'U0381889F',
    'UF39WLXAT',
    'UHGL04640',
    'UA7M10C0O',
    'UB51ZBPGJ',
    'UNS22LGIY',
    'UN0J0I7F0',
    'UH1039P7I',
    'UO513ARUP',
    'U3O3NUM10',
    'UKVN1ZI1Z',
    'ULAN263E4',
    'U7PX1XVTE',
    'UIDQ8QXI5',
    'UV4M04Y17',
    'U0D6182AR',
    'UC3Z15JC3',
    'U84A3Q05B',
    'UWW10VL06',
    'USI1BH3K3',
    'U2XQ3JJAN',
    'UYJ494VWS',
    'ULWL32B29',
    'U91Q0A72O',
    'U85PB3J63',
    'UA3IV9419',
    'UB9LLF16J',
    'U3U77Y17K',
    'U08ITMEA6',
]


def generate_reactions() -> list[dict]:
    """
    Generate a random list of reactions for a message.
    
    Returns a list of reaction dicts, each containing:
    - name: reaction name from REACTION_NAMES
    - users: list of user IDs who reacted
    - count: number of users (equals len(users))
    """
    # Randomly decide how many reaction types (0 to all available)
    # Weight towards fewer reactions (more realistic)
    num_reaction_types = random.choices(
        range(len(REACTION_NAMES) + 1),
        weights=[40, 25, 15, 10, 5, 3, 1, 0.5, 0.3, 0.2],  # Weighted towards 0-2 reactions
        k=1
    )[0]
    
    if num_reaction_types == 0:
        return []
    
    # Select which reaction types to include
    selected_reactions = random.sample(REACTION_NAMES, num_reaction_types)
    
    reactions = []
    for reaction_name in selected_reactions:
        # Randomly decide how many users reacted (1 to ~10 typically)
        # Weight towards fewer users per reaction
        num_users = random.choices(
            range(1, 11),
            weights=[40, 25, 15, 10, 5, 3, 1, 0.5, 0.3, 0.2],
            k=1
        )[0]
        
        # Select random users
        users = random.sample(MOCK_SLACK_USER_IDS, num_users)
        
        reactions.append({
            'name': reaction_name,
            'users': users,
            'count': len(users)
        })
    
    return reactions


def process_csv(input_path: Path, output_path: Path) -> None:
    """
    Read input CSV, generate reactions for each row, and write output CSV.
    """
    
    df = pd.read_csv(input_path)
    df['reactions'] = [json.dumps(generate_reactions()) for _ in range(len(df))]
    df.to_csv(output_path, index=False)
    
    print(f"Processed {len(df)} rows")
    print(f"Output written to: {output_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Generate mock reactions data for channel_messages CSV files."
    )
    parser.add_argument(
        "input_file",
        type=Path,
        help="Path to input CSV file containing channel_messages data"
    )
    parser.add_argument(
        "-o", "--output",
        type=Path,
        default=None,
        help="Path to output CSV file (default: input_file with '_with_reactions' suffix)"
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Random seed for reproducible results"
    )
    
    args = parser.parse_args()
    
    # Validate input file exists
    if not args.input_file.exists():
        print(f"Error: Input file not found: {args.input_file}")
        return 1
    
    # Set output path
    if args.output is None:
        output_path = args.input_file.with_stem(f"{args.input_file.stem}_with_reactions")
    else:
        output_path = args.output
    
    # Set random seed if provided
    if args.seed is not None:
        random.seed(args.seed)
    
    # Process the CSV
    process_csv(args.input_file, output_path)
    
    return 0


if __name__ == "__main__":
    exit(main())

