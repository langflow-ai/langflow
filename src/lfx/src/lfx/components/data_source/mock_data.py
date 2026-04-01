import secrets
from datetime import datetime, timedelta, timezone

from lfx.custom.custom_component.component import Component
from lfx.io import Output
from lfx.schema import Data, DataFrame
from lfx.schema.message import Message


class MockDataGeneratorComponent(Component):
    """Mock Data Generator Component.

    Generates sample data for testing and development purposes. Supports three main
    Langflow output types: Message (text), Data (JSON), and DataFrame (tabular data).

    This component is useful for:
    - Testing workflows without real data sources
    - Prototyping data processing pipelines
    - Creating sample data for demonstrations
    - Development and debugging of Langflow components
    """

    display_name = "Mock Data"
    description = "Generate mock data for testing and development."
    icon = "database"
    name = "MockDataGenerator"

    inputs = []

    outputs = [
        Output(display_name="Result", name="dataframe_output", method="generate_dataframe_output"),
        Output(display_name="Result", name="message_output", method="generate_message_output"),
        Output(display_name="Result", name="data_output", method="generate_data_output"),
    ]

    def build(self) -> DataFrame:
        """Default build method - returns DataFrame when component is standalone."""
        return self.generate_dataframe_output()

    def generate_message_output(self) -> Message:
        """Generate Message output specifically.

        Returns:
            Message: A Message object containing Lorem Ipsum text
        """
        try:
            self.log("Generating Message mock data")
            message = self._generate_message()
            self.status = f"Generated Lorem Ipsum message ({len(message.text)} characters)"
        except (ValueError, TypeError) as e:
            error_msg = f"Error generating Message data: {e!s}"
            self.log(error_msg)
            self.status = f"Error: {error_msg}"
            return Message(text=f"Error: {error_msg}")
        else:
            return message

    def generate_data_output(self) -> Data:
        """Generate Data output specifically.

        Returns:
            Data: A Data object containing sample JSON data (1 record)
        """
        try:
            record_count = 1  # Fixed to 1 record for Data output
            self.log(f"Generating Data mock data with {record_count} record")
            data = self._generate_data(record_count)
            self.status = f"Generated JSON data with {len(data.data.get('records', []))} record(s)"
        except (ValueError, TypeError) as e:
            error_msg = f"Error generating Data: {e!s}"
            self.log(error_msg)
            self.status = f"Error: {error_msg}"
            return Data(data={"error": error_msg, "success": False})
        else:
            return data

    def generate_dataframe_output(self) -> DataFrame:
        """Generate DataFrame output specifically.

        Returns:
            DataFrame: A Langflow DataFrame with sample data (50 records)
        """
        try:
            record_count = 50  # Fixed to 50 records for DataFrame output
            self.log(f"Generating DataFrame mock data with {record_count} records")
            return self._generate_dataframe(record_count)
        except (ValueError, TypeError) as e:
            error_msg = f"Error generating DataFrame: {e!s}"
            self.log(error_msg)

            try:
                import pandas as pd

                error_df = pd.DataFrame({"error": [error_msg]})
                return DataFrame(error_df)
            except ImportError:
                # Even without pandas, return DataFrame wrapper
                return DataFrame({"error": [error_msg]})

    def _generate_message(self) -> Message:
        """Generate a sample Message with Lorem Ipsum text.

        Returns:
            Message: A Message object containing Lorem Ipsum text
        """
        lorem_ipsum_texts = [
            (
                "Lorem ipsum dolor sit amet, consectetur adipiscing elit. Sed do eiusmod tempor "
                "incididunt ut labore et dolore magna aliqua. Ut enim ad minim veniam, quis nostrud "
                "exercitation ullamco laboris nisi ut aliquip ex ea commodo consequat."
            ),
            (
                "Duis aute irure dolor in reprehenderit in voluptate velit esse cillum dolore eu fugiat nulla "
                "pariatur. Excepteur sint occaecat cupidatat non proident, sunt in culpa qui officia deserunt "
                "mollit anim id est laborum."
            ),
            (
                "Sed ut perspiciatis unde omnis iste natus error sit voluptatem accusantium doloremque laudantium, "
                "totam rem aperiam, eaque ipsa quae ab illo inventore veritatis et quasi architecto "
                "beatae vitae dicta sunt explicabo."
            ),
            (
                "Nemo enim ipsam voluptatem quia voluptas sit aspernatur aut odit aut fugit, "
                "sed quia consequuntur magni dolores eos qui ratione voluptatem sequi nesciunt."
            ),
            (
                "Neque porro quisquam est, qui dolorem ipsum quia dolor sit amet, consectetur, "
                "adipisci velit, sed quia non numquam eius modi tempora incidunt ut labore et dolore "
                "magnam aliquam quaerat voluptatem."
            ),
        ]

        selected_text = secrets.choice(lorem_ipsum_texts)
        return Message(text=selected_text)

    def _generate_data(self, record_count: int) -> Data:
        """Generate sample Data with JSON structure.

        Args:
            record_count: Number of records to generate

        Returns:
            Data: A Data object containing sample JSON data
        """
        # Sample data categories
        companies = [
            "TechCorp",
            "DataSystems",
            "CloudWorks",
            "InnovateLab",
            "DigitalFlow",
            "SmartSolutions",
            "FutureTech",
            "NextGen",
        ]
        departments = ["Engineering", "Sales", "Marketing", "HR", "Finance", "Operations", "Support", "Research"]
        statuses = ["active", "pending", "completed", "cancelled", "in_progress"]
        categories = ["A", "B", "C", "D"]

        # Generate sample records
        records = []
        base_date = datetime.now(tz=timezone.utc) - timedelta(days=365)

        for i in range(record_count):
            record = {
                "id": f"REC-{1000 + i}",
                "name": f"Sample Record {i + 1}",
                "company": secrets.choice(companies),
                "department": secrets.choice(departments),
                "status": secrets.choice(statuses),
                "category": secrets.choice(categories),
                "value": round(secrets.randbelow(9901) + 100 + secrets.randbelow(100) / 100, 2),
                "quantity": secrets.randbelow(100) + 1,
                "rating": round(secrets.randbelow(41) / 10 + 1, 1),
                "is_active": secrets.choice([True, False]),
                "created_date": (base_date + timedelta(days=secrets.randbelow(366))).isoformat(),
                "tags": [
                    secrets.choice(
                        [
                            "important",
                            "urgent",
                            "review",
                            "approved",
                            "draft",
                            "final",
                        ]
                    )
                    for _ in range(secrets.randbelow(3) + 1)
                ],
            }
            records.append(record)

        # Create the main data structure
        data_structure = {
            "records": records,
            "summary": {
                "total_count": record_count,
                "active_count": sum(1 for r in records if r["is_active"]),
                "total_value": sum(r["value"] for r in records),
                "average_rating": round(sum(r["rating"] for r in records) / record_count, 2),
                "categories": list({r["category"] for r in records}),
                "companies": list({r["company"] for r in records}),
            },
        }

        return Data(data=data_structure)

    def _generate_dataframe(self, record_count: int) -> DataFrame:
        """Generate sample DataFrame with realistic business data.

        Args:
            record_count: Number of rows to generate

        Returns:
            DataFrame: A Langflow DataFrame with sample data
        """
        try:
            import pandas as pd

            self.log(f"pandas imported successfully, version: {pd.__version__}")
        except ImportError as e:
            self.log(f"pandas not available: {e!s}, creating simple DataFrame fallback")
            # Create a simple DataFrame-like structure without pandas
            data_result = self._generate_data(record_count)
            # Convert Data to simple DataFrame format
            try:
                # Create a basic DataFrame structure from the Data
                records = data_result.data.get("records", [])
                if records:
                    # Use first record to get column names
                    columns = list(records[0].keys()) if records else ["error"]
                    rows = [list(record.values()) for record in records]
                else:
                    columns = ["error"]
                    rows = [["pandas not available"]]

                # Create a simple dict-based DataFrame representation
                simple_df_data = {
                    col: [row[i] if i < len(row) else None for row in rows] for i, col in enumerate(columns)
                }

                # Return as DataFrame wrapper (Langflow will handle the display)
                return DataFrame(simple_df_data)
            except (ValueError, TypeError):
                # Ultimate fallback - return the Data as DataFrame
                return DataFrame({"data": [str(data_result.data)]})

        try:
            self.log(f"Starting DataFrame generation with {record_count} records")

            # Sample data for realistic business dataset
            first_names = [
                "John",
                "Jane",
                "Michael",
                "Sarah",
                "David",
                "Emily",
                "Robert",
                "Lisa",
                "William",
                "Jennifer",
            ]
            last_names = [
                "Smith",
                "Johnson",
                "Williams",
                "Brown",
                "Jones",
                "Garcia",
                "Miller",
                "Davis",
                "Rodriguez",
                "Martinez",
            ]
            cities = [
                "New York",
                "Los Angeles",
                "Chicago",
                "Houston",
                "Phoenix",
                "Philadelphia",
                "San Antonio",
                "San Diego",
                "Dallas",
                "San Jose",
            ]
            countries = ["USA", "Canada", "UK", "Germany", "France", "Australia", "Japan", "Brazil", "India", "Mexico"]
            products = [
                "Product A",
                "Product B",
                "Product C",
                "Product D",
                "Product E",
                "Service X",
                "Service Y",
                "Service Z",
            ]

            # Generate DataFrame data
            data = []
            base_date = datetime.now(tz=timezone.utc) - timedelta(days=365)

            self.log("Generating row data...")
            for i in range(record_count):
                row = {
                    "customer_id": f"CUST-{10000 + i}",
                    "first_name": secrets.choice(first_names),
                    "last_name": secrets.choice(last_names),
                    "email": f"user{i + 1}@example.com",
                    "age": secrets.randbelow(63) + 18,
                    "city": secrets.choice(cities),
                    "country": secrets.choice(countries),
                    "product": secrets.choice(products),
                    "order_date": (base_date + timedelta(days=secrets.randbelow(366))).strftime("%Y-%m-%d"),
                    "order_value": round(secrets.randbelow(991) + 10 + secrets.randbelow(100) / 100, 2),
                    "quantity": secrets.randbelow(10) + 1,
                    "discount": round(secrets.randbelow(31) / 100, 2),
                    "is_premium": secrets.choice([True, False]),
                    "satisfaction_score": secrets.randbelow(10) + 1,
                    "last_contact": (base_date + timedelta(days=secrets.randbelow(366))).strftime("%Y-%m-%d"),
                }
                data.append(row)
            # Create DataFrame
            self.log("Creating pandas DataFrame...")
            df = pd.DataFrame(data)
            self.log(f"DataFrame created with shape: {df.shape}")

            # Add calculated columns
            self.log("Adding calculated columns...")
            df["full_name"] = df["first_name"] + " " + df["last_name"]
            df["discounted_value"] = df["order_value"] * (1 - df["discount"])
            df["total_value"] = df["discounted_value"] * df["quantity"]

            # Age group boundaries as constants
            age_group_18_25 = 25
            age_group_26_35 = 35
            age_group_36_50 = 50
            age_group_51_65 = 65

            # Create age groups with better error handling
            try:
                df["age_group"] = pd.cut(
                    df["age"],
                    bins=[
                        0,
                        age_group_18_25,
                        age_group_26_35,
                        age_group_36_50,
                        age_group_51_65,
                        100,
                    ],
                    labels=[
                        "18-25",
                        "26-35",
                        "36-50",
                        "51-65",
                        "65+",
                    ],
                )
            except (ValueError, TypeError) as e:
                self.log(f"Error creating age groups with pd.cut: {e!s}, using simple categorization")
                df["age_group"] = df["age"].apply(
                    lambda x: "18-25"
                    if x <= age_group_18_25
                    else "26-35"
                    if x <= age_group_26_35
                    else "36-50"
                    if x <= age_group_36_50
                    else "51-65"
                    if x <= age_group_51_65
                    else "65+"
                )

            self.log(f"Successfully generated DataFrame with shape: {df.shape}, columns: {list(df.columns)}")
            # CRITICAL: Use DataFrame wrapper from Langflow
            # DO NOT set self.status when returning DataFrames - it interferes with display
            return DataFrame(df)

        except (ValueError, TypeError) as e:
            error_msg = f"Error generating DataFrame: {e!s}"
            self.log(error_msg)
            # DO NOT set self.status when returning DataFrames - it interferes with display
            # Return a fallback DataFrame with error info using Langflow wrapper
            try:
                error_df = pd.DataFrame(
                    {
                        "error": [error_msg],
                        "timestamp": [datetime.now(tz=timezone.utc).isoformat()],
                        "attempted_records": [record_count],
                    }
                )
                return DataFrame(error_df)
            except (ValueError, TypeError) as fallback_error:
                # Last resort: return simple error DataFrame
                self.log(f"Fallback also failed: {fallback_error!s}")
                simple_error_df = pd.DataFrame({"error": [error_msg]})
                return DataFrame(simple_error_df)
