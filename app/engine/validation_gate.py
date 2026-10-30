from __future__ import annotations
from datetime import date
from decimal import Decimal
from app.models.matrix import ValidationCheck, ValidationResult, WeeklyMatrix

class ValidationGate:

    def run(self, matrix: WeeklyMatrix, opening_cash_field_count: int=1) -> ValidationResult:
        checks: list[ValidationCheck] = []
        checks.append(self._check_recursion_integrity(matrix))
        checks.append(self._check_single_opening_cash_source(opening_cash_field_count))
        checks.append(self._check_routing_completeness(matrix))
        checks.append(self._check_no_null_confidence(matrix))
        all_passed = all((c.passed for c in checks))
        return ValidationResult(passed=all_passed, checks=checks)

    def _check_recursion_integrity(self, matrix: WeeklyMatrix) -> ValidationCheck:
        failures = []
        weeks = matrix.weeks
        for i in range(1, len(weeks)):
            prev_ending = weeks[i - 1].ending_cash
            cur_opening = weeks[i].opening_cash
            if cur_opening != prev_ending:
                failures.append(f'Week {i + 1} ({weeks[i].week_ending_friday}): Opening_Cash={cur_opening} ≠ prev Ending_Cash={prev_ending}')
        return ValidationCheck(name='recursion_integrity', passed=len(failures) == 0, message='Opening_Cash[t] == Ending_Cash[t-1] holds for all t > 1.' if not failures else f'Recursion integrity FAILED for {len(failures)} week(s).', details=failures)

    def _check_single_opening_cash_source(self, field_count: int) -> ValidationCheck:
        passed = field_count == 1
        return ValidationCheck(name='single_opening_cash_source', passed=passed, message='Exactly one writable Opening Cash field exists (structural check passed).' if passed else f'FAILED: found {field_count} writable Opening Cash fields. Design principle: there must be exactly one (Section 4.7).')

    def _check_routing_completeness(self, matrix: WeeklyMatrix) -> ValidationCheck:
        from app.config.loader import load_coa_routing
        coa = load_coa_routing()
        unrecognized: list[str] = []
        for ws in matrix.weeks:
            for field_name in ws.__dataclass_fields__:
                cell = getattr(ws, field_name, None)
                if hasattr(cell, 'line_items'):
                    for item in cell.line_items:
                        if item.coa_code not in coa.all_codes:
                            unrecognized.append(f"Week {ws.week_ending_friday}: COA code '{item.coa_code}' ('{item.label}') not in routing table.")
        return ValidationCheck(name='routing_completeness', passed=len(unrecognized) == 0, message='All COA codes resolve to a known routing table row.' if not unrecognized else f'FAILED: {len(unrecognized)} unrecognized COA code(s) — blocking.', details=unrecognized)

    def _check_no_null_confidence(self, matrix: WeeklyMatrix) -> ValidationCheck:
        null_refs: list[str] = []
        for ws in matrix.weeks:
            for field_name in ws.__dataclass_fields__:
                cell = getattr(ws, field_name, None)
                if hasattr(cell, 'line_items'):
                    for item in cell.line_items:
                        if item.confidence is None:
                            null_refs.append(f'Week {ws.week_ending_friday} / {field_name} / {item.label} ({item.raw_ref}): confidence is null.')
        return ValidationCheck(name='no_null_confidence', passed=len(null_refs) == 0, message='Every computed line item has a non-null data_confidence.' if not null_refs else f'FAILED: {len(null_refs)} line item(s) with null confidence — code bug.', details=null_refs)
