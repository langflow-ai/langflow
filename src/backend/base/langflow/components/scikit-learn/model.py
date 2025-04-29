import pandas as pd
from sklearn.base import BaseEstimator
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.linear_model import LinearRegression, LogisticRegression
from sklearn.svm import SVC, SVR
from sklearn.tree import DecisionTreeClassifier, DecisionTreeRegressor

from langflow.custom import Component
from langflow.io import DropdownInput, HandleInput, IntInput, MessageTextInput, Output
from langflow.schema import DataFrame


class SklearnModelComponent(Component):
    display_name = "Sklearn Model"
    description = "Train and use scikit-learn models"
    documentation = "https://scikit-learn.org/stable/supervised_learning.html"
    icon = "ScikitLearn"
    TrainedModel = None
    Predictions = None
    ModelPerformance = None

    AVAILABLE_MODELS = {
        "LogisticRegression": LogisticRegression,
        "RandomForestClassifier": RandomForestClassifier,
        "SVC": SVC,
        "DecisionTreeClassifier": DecisionTreeClassifier,
        "LinearRegression": LinearRegression,
        "RandomForestRegressor": RandomForestRegressor,
        "SVR": SVR,
        "DecisionTreeRegressor": DecisionTreeRegressor,
    }

    CLASSIFIER_MODELS = ["LogisticRegression", "RandomForestClassifier", "SVC", "DecisionTreeClassifier"]

    inputs = [
        HandleInput(name="train_data", display_name="Train Data", info="The training data", input_types=["DataFrame"]),
        HandleInput(name="test_data", display_name="Test Data", info="The test data", input_types=["DataFrame"]),
        DropdownInput(
            name="model_type",
            display_name="Model Type",
            options=list(AVAILABLE_MODELS.keys()),
            value="RandomForestClassifier",
            info="Select a scikit-learn model",
        ),
        IntInput(
            name="random_state",
            display_name="Random State",
            value=42,
            info="Random state for reproducibility",
        ),
        MessageTextInput(
            name="target_column",
            display_name="Target Column",
            info="The column name of the target variable",
            value="target",
        ),
    ]

    outputs = [
        Output(display_name="Trained Model", name="model", method="train_model"),
        Output(display_name="Predictions", name="predictions", method="predict"),
    ]

    def train_model(self) -> BaseEstimator:
        if not hasattr(self, "train_data"):
            msg = "No training data provided. Please connect a train-test split component."
            raise ValueError(msg)

        if not isinstance(self.train_data, DataFrame):
            msg = "The training data is not a DataFrame. Please connect a DataFrame component."
            raise TypeError(msg)
        if not isinstance(self.test_data, DataFrame):
            msg = "The test data is not a DataFrame. Please connect a DataFrame component."
            raise TypeError(msg)
        if self.target_column not in self.train_data.columns:
            msg = f"Error: The target column '{self.target_column}' does not exist in the training data."
            raise ValueError(msg)

        x_train = self.train_data.drop(self.target_column, axis=1)
        y_train = self.train_data[self.target_column]

        # Get the selected model class and create an instance
        model_class = self.AVAILABLE_MODELS[self.model_type]

        model = model_class()

        # Train the model
        model.fit(x_train, y_train)
        self.TrainedModel = model
        self.status = "Model trained successfully"
        return model

    def predict(self) -> DataFrame:
        self.train_model()
        if not hasattr(self, "TrainedModel"):
            msg = "No trained model provided. Please connect a train-test split component."
            raise ValueError(msg)
        if not isinstance(self.test_data, DataFrame):
            msg = "The test data is not a DataFrame. Please connect a DataFrame component."
            raise TypeError(msg)
        # Make predictions if test data is provided
        # if self.TrainedModel is None:
        # self.TrainedModel = self.train_model()
        self.test_x = self.test_data.drop(self.target_column, axis=1)
        self.test_y = self.test_data[self.target_column]
        predictions = self.TrainedModel.predict(self.test_x)
        # create a dataframe with the predictions
        predictions_df = pd.DataFrame(predictions, columns=["predictions"])
        result = DataFrame(predictions_df)
        self.status = result
        return result
