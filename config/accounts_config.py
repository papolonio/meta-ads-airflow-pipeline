import os
from typing import List, Dict, Tuple


class AccountsConfig:
    """Manages configuration for multiple Meta Ads accounts."""

    def __init__(self):
        """Initialize accounts configuration from environment variables."""
        self.tokens = self._load_tokens()
        self.accounts = self._load_accounts()

    def _load_tokens(self) -> List[str]:
        """
        Load Graph API tokens from environment variable.

        Returns:
            List of access tokens

        Raises:
            ValueError: If no tokens are configured
        """
        tokens_str = os.getenv('GRAPH_API_TOKENS', '')
        tokens = [token.strip() for token in tokens_str.split(',') if token.strip()]

        if not tokens:
            raise ValueError(
                "No Graph API tokens configured. "
                "Please set GRAPH_API_TOKENS environment variable."
            )

        return tokens

    def _load_accounts(self) -> List[Dict[str, str]]:
        """
        Load account configurations from environment variable.

        Expected format: account_id_1:table_name_1,account_id_2:table_name_2,...

        Returns:
            List of account configuration dictionaries

        Raises:
            ValueError: If accounts configuration is invalid
        """
        accounts_str = os.getenv('META_ACCOUNTS', '')
        accounts = []

        if not accounts_str:
            raise ValueError(
                "No Meta accounts configured. "
                "Please set META_ACCOUNTS environment variable."
            )

        for item in accounts_str.split(','):
            item = item.strip()
            if not item:
                continue

            try:
                account_id, table_name = item.split(':')
                accounts.append({
                    'account_id': account_id.strip(),
                    'table': table_name.strip()
                })
            except ValueError:
                raise ValueError(
                    f"Invalid account configuration format: '{item}'. "
                    f"Expected format: account_id:table_name"
                )

        if not accounts:
            raise ValueError("No valid Meta accounts found in configuration.")

        return accounts

    def get_account_with_token(self, account_index: int) -> Tuple[Dict[str, str], str]:
        """
        Get account configuration with its associated token.

        Implements token rotation across accounts.

        Args:
            account_index: Index of the account

        Returns:
            Tuple of (account_dict, token_string)

        Raises:
            IndexError: If account_index is out of range
        """
        if account_index >= len(self.accounts):
            raise IndexError(f"Account index {account_index} out of range")

        account = self.accounts[account_index]
        # Rotate tokens across accounts
        token = self.tokens[account_index % len(self.tokens)]

        return account, token

    def get_accounts_chunk(self, start_idx: int, end_idx: int) -> List[Dict[str, str]]:
        """
        Get a slice of accounts for parallel processing.

        Args:
            start_idx: Starting index (inclusive)
            end_idx: Ending index (exclusive)

        Returns:
            List of account configurations
        """
        return self.accounts[start_idx:end_idx]

    def split_accounts_into_groups(self, num_groups: int = 2) -> List[List[Dict[str, str]]]:
        """
        Split accounts into groups for parallel task execution.

        Args:
            num_groups: Number of groups to create

        Returns:
            List of account groups
        """
        total_accounts = len(self.accounts)
        accounts_per_group = (total_accounts + num_groups - 1) // num_groups

        groups = []
        for i in range(0, total_accounts, accounts_per_group):
            groups.append(self.accounts[i:i + accounts_per_group])

        return groups

    def get_total_accounts(self) -> int:
        """Get total number of configured accounts."""
        return len(self.accounts)

    def get_total_tokens(self) -> int:
        """Get total number of configured tokens."""
        return len(self.tokens)

    def validate_configuration(self) -> bool:
        """
        Validate that the configuration is complete and valid.

        Returns:
            True if configuration is valid

        Raises:
            ValueError: If configuration is invalid
        """
        if not self.accounts:
            raise ValueError("No accounts configured")

        if not self.tokens:
            raise ValueError("No tokens configured")

        # Check for duplicate account IDs
        account_ids = [acc['account_id'] for acc in self.accounts]
        if len(account_ids) != len(set(account_ids)):
            raise ValueError("Duplicate account IDs found in configuration")

        # Check for duplicate table names
        table_names = [acc['table'] for acc in self.accounts]
        if len(table_names) != len(set(table_names)):
            raise ValueError("Duplicate table names found in configuration")

        return True
