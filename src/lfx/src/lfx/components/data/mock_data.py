from typing import Any, Dict, List, Union
import pandas as pd
from datetime import datetime, timedelta
import random

from langflow.custom.custom_component.component import Component
from langflow.io import DropdownInput, IntInput, Output, BoolInput
from langflow.schema import Data, DataFrame
from langflow.schema.message import Message


class MockDataGeneratorComponent(Component):
    """Mock Data Generator Component
    
    Generates sample data for testing and development purposes. Supports three main 
    Langflow output types: Message (text), Data (JSON), and DataFrame (tabular data).
    
    This component is useful for:
    - Testing workflows without real data sources
    - Prototyping data processing pipelines
    - Creating sample data for demonstrations
    - Development and debugging of Langflow components
    """

    display_name = "Mock Data Generator"
    description = "Generate sample data for testing and development. Choose from text messages, JSON data, or tabular data formats."
    icon = "database"
    name = "MockDataGenerator"

    inputs = []

    outputs = [
        Output(display_name="DataFrame Output", name="dataframe_output", method="generate_dataframe_output"),
        Output(display_name="Message Output", name="message_output", method="generate_message_output"),
        Output(display_name="Data Output", name="data_output", method="generate_data_output"),
    ]
    
    def build(self) -> DataFrame:
        """Default build method - returns DataFrame when component is standalone"""
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
            return message
        except Exception as e:
            error_msg = f"Error generating Message data: {str(e)}"
            self.log(error_msg)
            self.status = f"Error: {error_msg}"
            return Message(text=f"Error: {error_msg}")
    
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
            return data
        except Exception as e:
            error_msg = f"Error generating Data: {str(e)}"
            self.log(error_msg)
            self.status = f"Error: {error_msg}"
            return Data(data={"error": error_msg, "success": False})
    
    def generate_dataframe_output(self) -> DataFrame:
        """Generate DataFrame output specifically.
        
        Returns:
            DataFrame: A Langflow DataFrame with sample data (50 records)
        """
        try:
            record_count = 50  # Fixed to 50 records for DataFrame output
            self.log(f"Generating DataFrame mock data with {record_count} records")
            return self._generate_dataframe(record_count)
        except Exception as e:
            error_msg = f"Error generating DataFrame: {str(e)}"
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
            "Lorem ipsum dolor sit amet, consectetur adipiscing elit. Sed do eiusmod tempor incididunt ut labore et dolore magna aliqua. Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo consequat.",
            "Duis aute irure dolor in reprehenderit in voluptate velit esse cillum dolore eu fugiat nulla pariatur. Excepteur sint occaecat cupidatat non proident, sunt in culpa qui officia deserunt mollit anim id est laborum.",
            "Sed ut perspiciatis unde omnis iste natus error sit voluptatem accusantium doloremque laudantium, totam rem aperiam, eaque ipsa quae ab illo inventore veritatis et quasi architecto beatae vitae dicta sunt explicabo.",
            "Nemo enim ipsam voluptatem quia voluptas sit aspernatur aut odit aut fugit, sed quia consequuntur magni dolores eos qui ratione voluptatem sequi nesciunt.",
            "Neque porro quisquam est, qui dolorem ipsum quia dolor sit amet, consectetur, adipisci velit, sed quia non numquam eius modi tempora incidunt ut labore et dolore magnam aliquam quaerat voluptatem."
        ]
        
        selected_text = random.choice(lorem_ipsum_texts)
        return Message(text=selected_text)

    def _generate_data(self, record_count: int) -> Data:
        """Generate sample Data with JSON structure.
        
        Args:
            record_count: Number of records to generate
            
        Returns:
            Data: A Data object containing sample JSON data
        """
        # Sample data categories
        companies = ["TechCorp", "DataSystems", "CloudWorks", "InnovateLab", "DigitalFlow", "SmartSolutions", "FutureTech", "NextGen"]
        departments = ["Engineering", "Sales", "Marketing", "HR", "Finance", "Operations", "Support", "Research"]
        statuses = ["active", "pending", "completed", "cancelled", "in_progress"]
        categories = ["A", "B", "C", "D"]
        
        # Generate sample records
        records = []
        base_date = datetime.now() - timedelta(days=365)
        
        for i in range(record_count):
            record = {
                "id": f"REC-{1000 + i}",
                "name": f"Sample Record {i + 1}",
                "company": random.choice(companies),
                "department": random.choice(departments),
                "status": random.choice(statuses),
                "category": random.choice(categories),
                "value": round(random.uniform(100, 10000), 2),
                "quantity": random.randint(1, 100),
                "rating": round(random.uniform(1, 5), 1),
                "is_active": random.choice([True, False]),
                "created_date": (base_date + timedelta(days=random.randint(0, 365))).isoformat(),
                "tags": random.sample(["important", "urgent", "review", "approved", "draft", "final"], k=random.randint(1, 3))
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
                "categories": list(set(r["category"] for r in records)),
                "companies": list(set(r["company"] for r in records))
            }
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
            self.log(f"pandas not available: {str(e)}, creating simple DataFrame fallback")
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
                simple_df_data = {col: [row[i] if i < len(row) else None for row in rows] 
                                 for i, col in enumerate(columns)}
                
                # Return as DataFrame wrapper (Langflow will handle the display)
                return DataFrame(simple_df_data)
            except Exception:
                # Ultimate fallback - return the Data as DataFrame
                return DataFrame({"data": [str(data_result.data)]})
        
        try:
            self.log(f"Starting DataFrame generation with {record_count} records")
            
            # Sample data for realistic business dataset
            first_names = ["John", "Jane", "Michael", "Sarah", "David", "Emily", "Robert", "Lisa", "William", "Jennifer"]
            last_names = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis", "Rodriguez", "Martinez"]
            cities = ["New York", "Los Angeles", "Chicago", "Houston", "Phoenix", "Philadelphia", "San Antonio", "San Diego", "Dallas", "San Jose"]
            countries = ["USA", "Canada", "UK", "Germany", "France", "Australia", "Japan", "Brazil", "India", "Mexico"]
            products = ["Product A", "Product B", "Product C", "Product D", "Product E", "Service X", "Service Y", "Service Z"]
            
            # Generate DataFrame data
            data = []
            base_date = datetime.now() - timedelta(days=365)
            
            self.log("Generating row data...")
            for i in range(record_count):
                row = {
                    "customer_id": f"CUST-{10000 + i}",
                    "first_name": random.choice(first_names),
                    "last_name": random.choice(last_names),
                    "email": f"user{i+1}@example.com",
                    "age": random.randint(18, 80),
                    "city": random.choice(cities),
                    "country": random.choice(countries),
                    "product": random.choice(products),
                    "order_date": (base_date + timedelta(days=random.randint(0, 365))).strftime("%Y-%m-%d"),
                    "order_value": round(random.uniform(10, 1000), 2),
                    "quantity": random.randint(1, 10),
                    "discount": round(random.uniform(0, 0.3), 2),
                    "is_premium": random.choice([True, False]),
                    "satisfaction_score": random.randint(1, 10),
                    "last_contact": (base_date + timedelta(days=random.randint(0, 365))).strftime("%Y-%m-%d")
                }
                data.append(row)
            
            self.log(f"Generated {len(data)} rows of data")
            
            # Create DataFrame
            self.log("Creating pandas DataFrame...")
            df = pd.DataFrame(data)
            self.log(f"DataFrame created with shape: {df.shape}")
            
            # Add calculated columns
            self.log("Adding calculated columns...")
            df["full_name"] = df["first_name"] + " " + df["last_name"]
            df["discounted_value"] = df["order_value"] * (1 - df["discount"])
            df["total_value"] = df["discounted_value"] * df["quantity"]
            
            # Create age groups with better error handling
            try:
                df["age_group"] = pd.cut(df["age"], bins=[0, 25, 35, 50, 65, 100], labels=["18-25", "26-35", "36-50", "51-65", "65+"])
            except Exception as e:
                self.log(f"Error creating age groups with pd.cut: {str(e)}, using simple categorization")
                df["age_group"] = df["age"].apply(lambda x: "18-25" if x <= 25 else "26-35" if x <= 35 else "36-50" if x <= 50 else "51-65" if x <= 65 else "65+")
            
            self.log(f"Successfully generated DataFrame with shape: {df.shape}, columns: {list(df.columns)}")
            # CRITICAL: Use DataFrame wrapper from Langflow
            # DO NOT set self.status when returning DataFrames - it interferes with display
            return DataFrame(df)
            
        except Exception as e:
            error_msg = f"Error generating DataFrame: {str(e)}"
            self.log(error_msg)
            # DO NOT set self.status when returning DataFrames - it interferes with display
            # Return a fallback DataFrame with error info using Langflow wrapper
            try:
                error_df = pd.DataFrame({
                    "error": [error_msg],
                    "timestamp": [datetime.now().isoformat()],
                    "attempted_records": [record_count]
                })
                return DataFrame(error_df)
            except Exception as fallback_error:
                # Last resort: return simple error DataFrame
                self.log(f"Fallback also failed: {str(fallback_error)}")
                simple_error_df = pd.DataFrame({"error": [error_msg]})
                return DataFrame(simple_error_df)

