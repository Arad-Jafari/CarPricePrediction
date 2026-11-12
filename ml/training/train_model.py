
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import joblib
from pathlib import Path

from sklearn.linear_model import LinearRegression
from sklearn.metrics import (
    mean_absolute_error,
    mean_squared_error,
    r2_score
)

from ml.data_cleaning.data_preprocessing import preprocess_data, preprocess_full_data

ARTIFACT_DIR = Path(__file__).resolve().parents[1] / "artifacts"


class ModelTrainingAndEvaluation:

    def __init__(self):
        self.model = None
        self.preprocessor = None
        self.y_test = None
        self.y_hat = None
        self.x_test_original = None
        self.final_df = None

    def train_model(self):

        # 1. Load and preprocess data
        (
            self.x_train,
            self.x_test,
            self.y_train,
            self.y_test,
            self.preprocessor,
            self.x_test_original,
        ) = preprocess_data()

        # 2. Initialize the model
        self.model = LinearRegression()

        # 3. Train the model
        self.model.fit(self.x_train, self.y_train)

        # 4. Make predictions
        self.y_hat = self.model.predict(self.x_test)

        return self.model, self.preprocessor

    def evaluate_model(self):

        # Ensure the model has been trained
        if self.model is None:
            raise ValueError("Train the model before evaluating it.")

        # 5. Evaluate the model
        mae = mean_absolute_error(self.y_test, self.y_hat)
        mse = mean_squared_error(self.y_test, self.y_hat)
        rmse = mean_squared_error(self.y_test, self.y_hat) ** 0.5
        r2 = r2_score(self.y_test, self.y_hat)

        mae_percentage = (mae / self.y_test.mean()) * 100
        approximate_accuracy = 100 - mae_percentage

        # 6. Display evaluation results
        print("\nModel Evaluation:")
        print(f"MAE: {mae:,.2f}")
        print(f"MSE: {mse:,.2f}")
        print(f"RMSE: {rmse:,.2f}")
        print(f"R-squared: {r2:.4f}")
        print(f"Approximate Accuracy: {approximate_accuracy:.2f}%")

        # 7. Create prediction evaluation DataFrame
        self.final_df = pd.DataFrame({
            "Actual Price": self.y_test,
            "Predicted Price": self.y_hat
        }, index=self.y_test.index)

        # 8. Calculate prediction errors
        self.final_df["Error"] = (
            self.final_df["Actual Price"] -
            self.final_df["Predicted Price"]
        )

        self.final_df["Absolute Error"] = (
            self.final_df["Error"].abs()
        )

        # 9. Add original car specifications
        self.final_df = pd.concat(
            [self.x_test_original, self.final_df],
            axis=1
        )

        # 10. Sort by largest prediction errors
        self.final_df = self.final_df.sort_values(
            by="Absolute Error",
            ascending=False
        )

        # 11. Plot 1: Actual vs Predicted Prices
        plt.figure(figsize=(8, 6))

        sns.scatterplot(
            data=self.final_df,
            x="Actual Price",
            y="Predicted Price"
        )

        min_price = min(
            self.final_df["Actual Price"].min(),
            self.final_df["Predicted Price"].min()
        )

        max_price = max(
            self.final_df["Actual Price"].max(),
            self.final_df["Predicted Price"].max()
        )

        plt.plot(
            [min_price, max_price],
            [min_price, max_price],
            linestyle="--",
            color="red",
            label="Perfect Prediction"
        )

        plt.title("Actual vs Predicted Car Prices")
        plt.xlabel("Actual Price")
        plt.ylabel("Predicted Price")
        plt.legend()
        plt.grid(alpha=0.3)
        plt.tight_layout()
        plt.show()

        # 12. Plot 2: Distribution of Prediction Errors
        plt.figure(figsize=(8, 6))

        sns.histplot(
            data=self.final_df,
            x="Error",
            bins=30,
            kde=True
        )

        plt.axvline(0, color="red", linestyle="--")

        plt.title("Distribution of Prediction Errors")
        plt.xlabel("Prediction Error (Actual - Predicted)")
        plt.ylabel("Number of Cars")
        plt.grid(alpha=0.3)
        plt.tight_layout()
        plt.show()

        return self.final_df


    def train_final_model(self):

        self.X, self.y, self.preprocessor = preprocess_full_data()

        # Train the final model on the entire dataset
        self.model = LinearRegression()
        self.model.fit(self.X, self.y)

        # Save the model and preprocessor
        ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
        joblib.dump(self.model, ARTIFACT_DIR / "CarPredictionModel.pkl")
        joblib.dump(self.preprocessor, ARTIFACT_DIR / "CarPreprocessor.pkl")

        print("Final model trained and saved successfully!")

if __name__ == "__main__":

    model_training = ModelTrainingAndEvaluation()

    model_training.train_model()

    model_training.evaluate_model()

    model_training.train_final_model()
