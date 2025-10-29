"""TSV parser for agent data."""

import csv
import logging
from pathlib import Path
from typing import Iterator, List

from .models import AgentData


logger = logging.getLogger(__name__)


class TSVParser:
    """Parser for agent TSV data."""

    def __init__(self, file_path: str):
        self.file_path = Path(file_path)
        if not self.file_path.exists():
            raise FileNotFoundError(f"TSV file not found: {file_path}")

    def parse_agents(self) -> List[AgentData]:
        """Parse all agents from TSV file."""
        agents = []
        errors = []

        for row_num, agent_data in enumerate(self._read_tsv(), start=2):  # Start at 2 (header is row 1)
            try:
                agents.append(agent_data)
            except Exception as e:
                error_msg = f"Row {row_num}: Failed to parse agent data - {e}"
                errors.append(error_msg)
                logger.warning(error_msg)

        if errors:
            logger.warning(f"Found {len(errors)} parsing errors out of {len(agents) + len(errors)} total rows")
            for error in errors[:5]:  # Log first 5 errors
                logger.warning(error)

        logger.info(f"Successfully parsed {len(agents)} agents from {self.file_path}")
        return agents

    def _read_tsv(self) -> Iterator[AgentData]:
        """Read and parse TSV file row by row."""
        with open(self.file_path, 'r', encoding='utf-8') as file:
            # Use csv.DictReader for TSV format
            reader = csv.DictReader(file, delimiter='\t')

            for row in reader:
                try:
                    agent_data = self._parse_row(row)
                    yield agent_data
                except Exception as e:
                    logger.error(f"Failed to parse row {reader.line_num}: {e}")
                    raise

    def _parse_row(self, row: dict) -> AgentData:
        """Parse a single TSV row into AgentData."""
        # Convert Y/N strings to boolean
        def parse_bool(value: str) -> bool:
            return value.strip().upper() == 'Y'

        try:
            return AgentData(
                domain_area=row['Domain Area'].strip(),
                agent_name=row['Agent Name'].strip(),
                description=row['Description'].strip(),
                applicable_to_payers=parse_bool(row['Applicable to Payers']),
                applicable_to_payviders=parse_bool(row['Applicable to Payviders']),
                applicable_to_providers=parse_bool(row['Applicable to Providers']),
                connectors=row['Connectors'].strip(),
                goals=row['Goals'].strip(),
                kpis=row['KPIs'].strip(),
                tools=row['Tools'].strip()
            )
        except KeyError as e:
            raise ValueError(f"Missing required column: {e}")
        except Exception as e:
            raise ValueError(f"Failed to parse row data: {e}")

    def validate_file_structure(self) -> List[str]:
        """Validate TSV file has required columns."""
        required_columns = {
            'Domain Area', 'Agent Name', 'Description',
            'Applicable to Payers', 'Applicable to Payviders', 'Applicable to Providers',
            'Connectors', 'Goals', 'KPIs', 'Tools'
        }

        errors = []

        try:
            with open(self.file_path, 'r', encoding='utf-8') as file:
                reader = csv.reader(file, delimiter='\t')
                header = next(reader)
                actual_columns = set(col.strip() for col in header)

                missing_columns = required_columns - actual_columns
                if missing_columns:
                    errors.append(f"Missing required columns: {missing_columns}")

                extra_columns = actual_columns - required_columns
                if extra_columns:
                    logger.info(f"Found additional columns: {extra_columns}")

        except Exception as e:
            errors.append(f"Failed to read file header: {e}")

        return errors