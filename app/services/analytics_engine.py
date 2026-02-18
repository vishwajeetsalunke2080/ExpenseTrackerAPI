"""Natural Language Analytics Engine for expense tracking queries."""
from typing import Dict, Any, Optional, List
from groq import AsyncGroq
from datetime import datetime, date
from decimal import Decimal
from collections import defaultdict
import json
import calendar
from ..services.expense_service import ExpenseService
from ..services.income_service import IncomeService
from ..schemas.filter import ExpenseFilter


class AnalyticsEngine:
    """
    Analytics engine that processes natural language queries about expenses.
    
    Uses LLM to parse queries and extract structured parameters, then executes
    analytics queries against expense data.
    """
    
    def __init__(self, groq_client: AsyncGroq, expense_service: ExpenseService, income_service: IncomeService, model: str = "llama-3.3-70b-versatile"):
        """
        Initialize the analytics engine.
        
        Args:
            groq_client: Async Groq client for LLM queries
            expense_service: Service for querying expense data
            income_service: Service for querying income data
            model: Groq model to use for queries
        """
        self.client = groq_client
        self.expense_service = expense_service
        self.income_service = income_service
        self.model = model
    
    async def process_query(self, query: str) -> Dict[str, Any]:
        """
        Process natural language query and return analytics results.
        
        Steps:
        1. Parse query using LLM to extract intent and parameters
        2. Convert to structured filter/aggregation
        3. Execute query against expense data
        4. Format results for human consumption
        
        Args:
            query: Natural language query from user
            
        Returns:
            Dictionary containing analytics results
            
        Raises:
            ValueError: If query cannot be parsed or understood
        """
        try:
            # Parse the query to extract structured parameters
            parsed_query = await self._parse_query(query)
            
            # Execute analytics based on parsed parameters
            results = await self._execute_analytics(parsed_query)
            
            # Format results for human consumption
            formatted_results = await self._format_results(results, query)
            
            return formatted_results
        except ValueError:
            # Re-raise ValueError as-is (these have helpful messages)
            raise
        except Exception as e:
            # Catch any unexpected errors and provide helpful message
            raise ValueError(
                "An error occurred while processing your query. "
                "Please try rephrasing your question or simplifying your request. "
                "If the problem persists, try a basic query like:\n"
                "  • 'What are my total expenses for November?'\n"
                "  • 'Show me spending by category'"
            ) from e
    
    async def _parse_query(self, query: str) -> Dict[str, Any]:
        """
        Use LLM to extract structured parameters from natural language query.

        Extracts:
        - time_period: {start_date, end_date} in ISO format
        - categories: list of expense categories
        - aggregation: "by_category", "by_account", "by_month", "total"
        - accounts: list of accounts

        Args:
            query: Natural language query from user

        Returns:
            Dictionary with extracted parameters

        Raises:
            ValueError: If query cannot be parsed with helpful suggestions
        """
        system_prompt = """ You are a query parser for an expense tracking system.

Your job is to extract structured filters from natural language queries.
Return ONLY valid JSON. Do not include explanation or extra text.

Timezone: Asia/Kolkata (IST)
All date calculations must use CURRENT_DATE in IST.

--------------------------------------------------
FIELDS TO EXTRACT
--------------------------------------------------

- intent: one of ["expense", "income"]
- time_period: {start_date, end_date} in ISO format (YYYY-MM-DD)
- categories: list of categories mentioned (e.g., ["Food", "Travel"])
- aggregation: one of ["by_category", "by_account", "by_month", "total", "by_week", "by_day", "by_intent"]
- accounts: list of accounts mentioned (e.g., ["Cash", "Card"])

If a field is not present in the query, omit it or set it to null.

If aggregation is not mentioned, default to "total".

--------------------------------------------------
INTENT NORMALIZATION (STRICT)
--------------------------------------------------

Map user language to intent as follows:

expense keywords:
spend, spent, spending, expense, expenses, paid, purchase, cost, debit, bill

income keywords:
income, earn, earned, salary, credit, received, gain, revenue

If intent cannot be determined, omit it.

--------------------------------------------------
RELATIVE DATE INTERPRETATION RULES (STRICT)
--------------------------------------------------

Resolve all relative time expressions using CURRENT_DATE in IST.

"today"
    start_date = CURRENT_DATE
    end_date = CURRENT_DATE

"yesterday"
    start_date = CURRENT_DATE - 1 day
    end_date = CURRENT_DATE - 1 day

"till today", "until today"
    end_date = CURRENT_DATE
    (omit start_date if not specified)

"this month"
    start_date = first day of CURRENT_DATE's month
    end_date = CURRENT_DATE

"last month"
    start_date = first day of previous month
    end_date = last day of previous month

"last N months"
    start_date = CURRENT_DATE shifted back by N months
    end_date = CURRENT_DATE

"past N days"
    start_date = CURRENT_DATE - N days
    end_date = CURRENT_DATE

"this year"
    start_date = YYYY-01-01 of CURRENT_DATE
    end_date = CURRENT_DATE

"last year"
    start_date = Jan 1 of previous year
    end_date = Dec 31 of previous year

If only a calendar month is mentioned (e.g., "December 2024"):
    use the first and last day of that month.

Never guess dates. Always compute deterministically.

--------------------------------------------------
CATEGORY + ACCOUNT EXTRACTION
--------------------------------------------------

Extract category/account names exactly as spoken.
Do not infer new ones.

--------------------------------------------------
AGGREGATION DETECTION
--------------------------------------------------

"by category", "category wise" → by_category
"by account" → by_account
"monthly", "per month" → by_month
"weekly" → by_week
"daily" → by_day
"overall", "total", or unspecified → total

--------------------------------------------------
OUTPUT FORMAT
--------------------------------------------------

Return JSON only. Example structure:

{
  "intent": "expense",
  "time_period": {"start_date": "2026-02-01", "end_date": "2026-02-17"},
  "categories": ["Food"],
  "aggregation": "total"
}

Do not include null keys unless necessary.

--------------------------------------------------
EXAMPLES
--------------------------------------------------

Query: "What are my spends this month?"
Response:
{
  "intent": "expense",
  "time_period": {"start_date": "2026-02-01", "end_date": "2026-02-17"},
  "aggregation": "total"
}

Query: "My total spends till today"
Response:
{
  "intent": "expense",
  "time_period": {"end_date": "2026-02-17"},
  "aggregation": "total"
}

Query: "My income in last 3 months"
Response:
{
  "intent": "income",
  "time_period": {"start_date": "2025-11-17", "end_date": "2026-02-17"},
  "aggregation": "total"
}

Query: "Show me Food expenses paid using Card past 7 days"
Response:
{
  "intent": "expense",
  "time_period": {"start_date": "2026-02-10", "end_date": "2026-02-17"},
  "categories": ["Food"],
  "accounts": ["Card"],
  "aggregation": "total"
}
"""

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": query}
                ],
                response_format={"type": "json_object"}
            )

            parsed = json.loads(response.choices[0].message.content)

            # Validate that we got at least some useful information
            if not parsed or (not parsed.get('aggregation') and 
                            not parsed.get('time_period') and 
                            not parsed.get('categories') and 
                            not parsed.get('intent') and 
                            not parsed.get('accounts')):
                raise ValueError("Query did not contain recognizable expense tracking parameters")

            return parsed

        except json.JSONDecodeError as e:
            raise ValueError(
                "Unable to parse query - received invalid response format. "
                "Please try rephrasing your question more clearly. "
                "Examples:\n"
                "  • 'What are my expenses for November by category?'\n"
                "  • 'Show me total spending on Food and Travel'\n"
                "  • 'How much did I spend using Card in December?'\n"
                "  • 'What are my monthly expenses for 2024?'\n"
                "  • 'How much did I earn last month?'\n"
                "  • 'Show me my income for February 2026'"
            ) from e
        except (KeyError, AttributeError, IndexError) as e:
            raise ValueError(
                "Unable to parse query - unexpected response structure. "
                "Please try rephrasing your question. "
                "Examples:\n"
                "  • 'What are my expenses for November by category?'\n"
                "  • 'Show me total spending on Food and Travel'\n"
                "  • 'How much did I spend using Card in December?'\n"
                "  • 'How much did I earn last month?'\n"
                "  • 'Show me my income for February 2026'"
            ) from e
        except ValueError as e:
            # Re-raise ValueError with additional context if it's our validation error
            if "recognizable expense tracking parameters" in str(e):
                raise ValueError(
                    "Unable to understand your query. Please include specific details about what you want to know. "
                    "Your query should mention:\n"
                    "  • A time period (e.g., 'November', 'last month', 'February 2026')\n"
                    "  • What you want to see (e.g., 'total spending', 'total income', 'breakdown by category')\n"
                    "  • Optionally: specific categories (e.g., 'Food', 'Travel', 'Salary')\n"
                    "  • Optionally: specific accounts (e.g., 'Card', 'Cash')\n\n"
                    "Example queries:\n"
                    "  • 'What are my expenses for November by category?'\n"
                    "  • 'Show me total spending on Food and Travel'\n"
                    "  • 'How much did I spend using Card in December?'\n"
                    "  • 'What are my monthly expenses for 2024?'\n"
                    "  • 'How much did I earn last month?'\n"
                    "  • 'Show me my income for February 2026'"
                ) from e
            raise
        except Exception as e:
            # Check if it's a Groq API error (be more specific)
            error_msg = str(e).lower()
            if any(keyword in error_msg for keyword in ['rate limit', 'quota exceeded', 'authentication', 'api key']):
                raise ValueError(
                    "Unable to process query due to service unavailability. "
                    "Please try again in a moment."
                ) from e

            # Generic error with helpful suggestions
            raise ValueError(
                "Unable to parse query. Please try rephrasing your question more clearly. "
                "Your query should include:\n"
                "  • A time period (e.g., 'November', 'last month', 'February 2026')\n"
                "  • What you want to see (e.g., 'total spending', 'total income', 'breakdown by category')\n"
                "  • Optionally: specific categories (e.g., 'Food', 'Travel', 'Salary')\n"
                "  • Optionally: specific accounts (e.g., 'Card', 'Cash')\n\n"
                "Example queries:\n"
                "  • 'What are my expenses for November by category?'\n"
                "  • 'Show me total spending on Food and Travel'\n"
                "  • 'How much did I spend using Card in December?'\n"
                "  • 'What are my monthly expenses for 2024?'\n"
                "  • 'How much did I earn last month?'\n"
                "  • 'Show me my income for February 2026'"
            ) from e


    
    async def _execute_analytics(self, parsed_query: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute the parsed query against expense or income data.
        
        Supports:
        - Category-based aggregation
        - Time-based aggregation (by month, week, day)
        - Querying both expenses and income based on intent
        
        Args:
            parsed_query: Structured parameters from _parse_query
            
        Returns:
            Dictionary containing query results with aggregated data
            
        Requirements: 6.2, 6.3
        """
        # Extract parameters from parsed query
        time_period = parsed_query.get('time_period', {})
        categories = parsed_query.get('categories')
        accounts = parsed_query.get('accounts')
        aggregation = parsed_query.get('aggregation', 'total')
        intent = parsed_query.get('intent', 'expense')  # Default to expense if not specified
        
        # Build filter for querying - use max page_size of 100
        filters = ExpenseFilter(
            start_date=datetime.fromisoformat(time_period['start_date']).date() if time_period.get('start_date') else None,
            end_date=datetime.fromisoformat(time_period['end_date']).date() if time_period.get('end_date') else None,
            categories=categories,
            accounts=accounts,
            page=1,
            page_size=100  # Max allowed by ExpenseFilter
        )
        
        # Fetch data based on intent
        expenses = []
        income_records = []
        
        if intent == 'income':
            # For income queries, only fetch income data
            if self.income_service:
                # Use same date filters but without accounts (income doesn't have accounts)
                income_filters = ExpenseFilter(
                    start_date=filters.start_date,
                    end_date=filters.end_date,
                    categories=categories,
                    page=1,
                    page_size=100
                )
                income_records = await self._fetch_all_income(income_filters)
        elif intent == 'expense':
            # For expense queries, only fetch expense data
            expenses = await self._fetch_all_expenses(filters)
        else:
            # For queries without specific intent or 'both', fetch both
            expenses = await self._fetch_all_expenses(filters)
            if self.income_service and aggregation in ['total', 'by_category', 'by_month']:
                income_filters = ExpenseFilter(
                    start_date=filters.start_date,
                    end_date=filters.end_date,
                    categories=categories,
                    page=1,
                    page_size=100
                )
                income_records = await self._fetch_all_income(income_filters)
        
        # Execute aggregation based on type
        if aggregation == 'by_category':
            return self._aggregate_by_category(expenses, income_records)
        elif aggregation == 'by_account':
            return self._aggregate_by_account(expenses)
        elif aggregation == 'by_month':
            return self._aggregate_by_month(expenses, income_records)
        elif aggregation == 'by_week':
            return self._aggregate_by_week(expenses)
        elif aggregation == 'by_day':
            return self._aggregate_by_day(expenses)
        else:  # 'total' or default
            return self._aggregate_total(expenses, income_records)
    
    async def _fetch_all_expenses(self, filters: ExpenseFilter) -> List:
        """Fetch all expenses by paginating through results.
        
        Args:
            filters: ExpenseFilter with initial filter parameters
            
        Returns:
            List of all expense records matching the filters
        """
        all_expenses = []
        page = 1
        
        while True:
            filters.page = page
            expenses, total = await self.expense_service.list_expenses(filters)
            all_expenses.extend(expenses)
            
            # Check if we've fetched all records
            if len(all_expenses) >= total:
                break
            
            page += 1
        
        return all_expenses
    
    async def _fetch_all_income(self, filters: ExpenseFilter) -> List:
        """Fetch all income records by paginating through results.
        
        Args:
            filters: ExpenseFilter with initial filter parameters
            
        Returns:
            List of all income records matching the filters
        """
        all_income = []
        page = 1
        
        while True:
            filters.page = page
            income_records, total = await self.income_service.list_income(filters)
            all_income.extend(income_records)
            
            # Check if we've fetched all records
            if len(all_income) >= total:
                break
            
            page += 1
        
        return all_income
    
    def _aggregate_by_category(self, expenses: List, income_records: List) -> Dict[str, Any]:
        """Aggregate expenses and income by category.
        
        Args:
            expenses: List of expense records
            income_records: List of income records
            
        Returns:
            Dictionary with category breakdowns
        """
        expense_by_category = defaultdict(Decimal)
        income_by_category = defaultdict(Decimal)
        
        for expense in expenses:
            expense_by_category[expense.category] += expense.amount
        
        for income in income_records:
            income_by_category[income.category] += income.amount
        
        return {
            'aggregation_type': 'by_category',
            'expenses': {cat: float(amt) for cat, amt in expense_by_category.items()},
            'income': {cat: float(amt) for cat, amt in income_by_category.items()},
            'total_expenses': float(sum(expense_by_category.values())),
            'total_income': float(sum(income_by_category.values()))
        }
    
    def _aggregate_by_account(self, expenses: List) -> Dict[str, Any]:
        """Aggregate expenses by account.
        
        Args:
            expenses: List of expense records
            
        Returns:
            Dictionary with account breakdowns
        """
        by_account = defaultdict(Decimal)
        
        for expense in expenses:
            by_account[expense.account] += expense.amount
        
        return {
            'aggregation_type': 'by_account',
            'accounts': {acc: float(amt) for acc, amt in by_account.items()},
            'total': float(sum(by_account.values()))
        }
    
    def _aggregate_by_month(self, expenses: List, income_records: List) -> Dict[str, Any]:
        """Aggregate expenses and income by month.
        
        Args:
            expenses: List of expense records
            income_records: List of income records
            
        Returns:
            Dictionary with monthly breakdowns
        """
        expense_by_month = defaultdict(Decimal)
        income_by_month = defaultdict(Decimal)
        
        for expense in expenses:
            month_key = expense.date.strftime('%Y-%m')
            expense_by_month[month_key] += expense.amount
        
        for income in income_records:
            month_key = income.date.strftime('%Y-%m')
            income_by_month[month_key] += income.amount
        
        # Combine all months and sort
        all_months = sorted(set(expense_by_month.keys()) | set(income_by_month.keys()))
        
        monthly_data = []
        for month in all_months:
            monthly_data.append({
                'month': month,
                'expenses': float(expense_by_month.get(month, Decimal(0))),
                'income': float(income_by_month.get(month, Decimal(0))),
                'net': float(income_by_month.get(month, Decimal(0)) - expense_by_month.get(month, Decimal(0)))
            })
        
        return {
            'aggregation_type': 'by_month',
            'data': monthly_data,
            'total_expenses': float(sum(expense_by_month.values())),
            'total_income': float(sum(income_by_month.values()))
        }
    
    def _aggregate_by_week(self, expenses: List) -> Dict[str, Any]:
        """Aggregate expenses by week.
        
        Args:
            expenses: List of expense records
            
        Returns:
            Dictionary with weekly breakdowns
        """
        by_week = defaultdict(Decimal)
        
        for expense in expenses:
            # Get ISO week number (year-week format)
            week_key = expense.date.strftime('%Y-W%W')
            by_week[week_key] += expense.amount
        
        weekly_data = [
            {'week': week, 'amount': float(amt)}
            for week, amt in sorted(by_week.items())
        ]
        
        return {
            'aggregation_type': 'by_week',
            'data': weekly_data,
            'total': float(sum(by_week.values()))
        }
    
    def _aggregate_by_day(self, expenses: List) -> Dict[str, Any]:
        """Aggregate expenses by day.
        
        Args:
            expenses: List of expense records
            
        Returns:
            Dictionary with daily breakdowns
        """
        by_day = defaultdict(Decimal)
        
        for expense in expenses:
            day_key = expense.date.isoformat()
            by_day[day_key] += expense.amount
        
        daily_data = [
            {'date': day, 'amount': float(amt)}
            for day, amt in sorted(by_day.items())
        ]
        
        return {
            'aggregation_type': 'by_day',
            'data': daily_data,
            'total': float(sum(by_day.values()))
        }
    
    def _aggregate_total(self, expenses: List, income_records: List) -> Dict[str, Any]:
        """Calculate total expenses and income.
        
        Args:
            expenses: List of expense records
            income_records: List of income records
            
        Returns:
            Dictionary with total amounts
        """
        total_expenses = sum(expense.amount for expense in expenses)
        total_income = sum(income.amount for income in income_records)
        
        return {
            'aggregation_type': 'total',
            'total_expenses': float(total_expenses),
            'total_income': float(total_income),
            'net': float(total_income - total_expenses),
            'expense_count': len(expenses),
            'income_count': len(income_records)
        }
    
    async def _format_results(self, results: Dict[str, Any], query: str) -> Dict[str, Any]:
        """
        Format results in human-readable form.
        
        Args:
            results: Raw query results
            query: Original user query
            
        Returns:
            Dictionary with formatted results including summary and breakdown
            
        Requirements: 6.5
        """
        aggregation_type = results.get('aggregation_type', 'total')
        
        # Handle empty results gracefully
        if aggregation_type == 'total':
            if results.get('expense_count', 0) == 0 and results.get('income_count', 0) == 0:
                return {
                    'query': query,
                    'summary': 'No transactions found for the specified criteria.',
                    'data': results
                }
        elif aggregation_type in ['by_category', 'by_account', 'by_month', 'by_week', 'by_day']:
            data_key = 'data' if 'data' in results else ('expenses' if 'expenses' in results else 'accounts')
            if not results.get(data_key):
                return {
                    'query': query,
                    'summary': 'No transactions found for the specified criteria.',
                    'data': results
                }
        
        # Format based on aggregation type
        if aggregation_type == 'by_category':
            return self._format_category_results(results, query)
        elif aggregation_type == 'by_account':
            return self._format_account_results(results, query)
        elif aggregation_type == 'by_month':
            return self._format_monthly_results(results, query)
        elif aggregation_type == 'by_week':
            return self._format_weekly_results(results, query)
        elif aggregation_type == 'by_day':
            return self._format_daily_results(results, query)
        else:  # 'total'
            return self._format_total_results(results, query)
    
    def _format_category_results(self, results: Dict[str, Any], query: str) -> Dict[str, Any]:
        """Format category-based aggregation results."""
        expenses = results.get('expenses', {})
        income = results.get('income', {})
        total_expenses = results.get('total_expenses', 0)
        total_income = results.get('total_income', 0)
        
        # Build summary
        summary_parts = []
        if total_expenses > 0:
            summary_parts.append(f"Total expenses: ${total_expenses:,.2f} across {len(expenses)} categories")
        if total_income > 0:
            summary_parts.append(f"Total income: ${total_income:,.2f} across {len(income)} categories")
        
        summary = '. '.join(summary_parts) if summary_parts else 'No transactions found.'
        
        # Build breakdown
        breakdown = []
        if expenses:
            breakdown.append("Expense Breakdown:")
            for category, amount in sorted(expenses.items(), key=lambda x: x[1], reverse=True):
                percentage = (amount / total_expenses * 100) if total_expenses > 0 else 0
                breakdown.append(f"  • {category}: ${amount:,.2f} ({percentage:.1f}%)")
        
        if income:
            if breakdown:
                breakdown.append("")
            breakdown.append("Income Breakdown:")
            for category, amount in sorted(income.items(), key=lambda x: x[1], reverse=True):
                percentage = (amount / total_income * 100) if total_income > 0 else 0
                breakdown.append(f"  • {category}: ${amount:,.2f} ({percentage:.1f}%)")
        
        return {
            'query': query,
            'summary': summary,
            'breakdown': '\n'.join(breakdown) if breakdown else 'No breakdown available.',
            'data': results
        }
    
    def _format_account_results(self, results: Dict[str, Any], query: str) -> Dict[str, Any]:
        """Format account-based aggregation results."""
        accounts = results.get('accounts', {})
        total = results.get('total', 0)
        
        summary = f"Total expenses: ${total:,.2f} across {len(accounts)} accounts" if total > 0 else 'No expenses found.'
        
        # Build breakdown
        breakdown = []
        if accounts:
            breakdown.append("Account Breakdown:")
            for account, amount in sorted(accounts.items(), key=lambda x: x[1], reverse=True):
                percentage = (amount / total * 100) if total > 0 else 0
                breakdown.append(f"  • {account}: ${amount:,.2f} ({percentage:.1f}%)")
        
        return {
            'query': query,
            'summary': summary,
            'breakdown': '\n'.join(breakdown) if breakdown else 'No breakdown available.',
            'data': results
        }
    
    def _format_monthly_results(self, results: Dict[str, Any], query: str) -> Dict[str, Any]:
        """Format monthly aggregation results."""
        monthly_data = results.get('data', [])
        total_expenses = results.get('total_expenses', 0)
        total_income = results.get('total_income', 0)
        
        summary_parts = []
        if total_expenses > 0:
            summary_parts.append(f"Total expenses: ${total_expenses:,.2f}")
        if total_income > 0:
            summary_parts.append(f"Total income: ${total_income:,.2f}")
        if total_expenses > 0 or total_income > 0:
            net = total_income - total_expenses
            net_label = "surplus" if net >= 0 else "deficit"
            summary_parts.append(f"Net {net_label}: ${abs(net):,.2f}")
        
        summary = ', '.join(summary_parts) if summary_parts else 'No transactions found.'
        summary += f" over {len(monthly_data)} months" if len(monthly_data) > 1 else ""
        
        # Build breakdown
        breakdown = []
        if monthly_data:
            breakdown.append("Monthly Breakdown:")
            for month_data in monthly_data:
                month = month_data['month']
                expenses = month_data['expenses']
                income = month_data['income']
                net = month_data['net']
                net_label = "surplus" if net >= 0 else "deficit"
                breakdown.append(f"  • {month}: Expenses ${expenses:,.2f}, Income ${income:,.2f}, Net {net_label} ${abs(net):,.2f}")
        
        return {
            'query': query,
            'summary': summary,
            'breakdown': '\n'.join(breakdown) if breakdown else 'No breakdown available.',
            'data': results
        }
    
    def _format_weekly_results(self, results: Dict[str, Any], query: str) -> Dict[str, Any]:
        """Format weekly aggregation results."""
        weekly_data = results.get('data', [])
        total = results.get('total', 0)
        
        summary = f"Total expenses: ${total:,.2f} over {len(weekly_data)} weeks" if total > 0 else 'No expenses found.'
        
        # Build breakdown
        breakdown = []
        if weekly_data:
            breakdown.append("Weekly Breakdown:")
            for week_data in weekly_data:
                week = week_data['week']
                amount = week_data['amount']
                breakdown.append(f"  • {week}: ${amount:,.2f}")
        
        return {
            'query': query,
            'summary': summary,
            'breakdown': '\n'.join(breakdown) if breakdown else 'No breakdown available.',
            'data': results
        }
    
    def _format_daily_results(self, results: Dict[str, Any], query: str) -> Dict[str, Any]:
        """Format daily aggregation results."""
        daily_data = results.get('data', [])
        total = results.get('total', 0)
        
        summary = f"Total expenses: ${total:,.2f} over {len(daily_data)} days" if total > 0 else 'No expenses found.'
        
        # Build breakdown
        breakdown = []
        if daily_data:
            breakdown.append("Daily Breakdown:")
            for day_data in daily_data:
                date = day_data['date']
                amount = day_data['amount']
                breakdown.append(f"  • {date}: ${amount:,.2f}")
        
        return {
            'query': query,
            'summary': summary,
            'breakdown': '\n'.join(breakdown) if breakdown else 'No breakdown available.',
            'data': results
        }
    
    def _format_total_results(self, results: Dict[str, Any], query: str) -> Dict[str, Any]:
        """Format total aggregation results."""
        total_expenses = results.get('total_expenses', 0)
        total_income = results.get('total_income', 0)
        net = results.get('net', 0)
        expense_count = results.get('expense_count', 0)
        income_count = results.get('income_count', 0)
        
        summary_parts = []
        if expense_count > 0:
            summary_parts.append(f"Total expenses: ${total_expenses:,.2f} ({expense_count} transactions)")
        if income_count > 0:
            summary_parts.append(f"Total income: ${total_income:,.2f} ({income_count} transactions)")
        if expense_count > 0 or income_count > 0:
            net_label = "surplus" if net >= 0 else "deficit"
            summary_parts.append(f"Net {net_label}: ${abs(net):,.2f}")
        
        summary = '. '.join(summary_parts) if summary_parts else 'No transactions found.'
        
        return {
            'query': query,
            'summary': summary,
            'data': results
        }
