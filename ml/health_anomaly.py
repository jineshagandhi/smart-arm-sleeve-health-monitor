import pandas as pd
import numpy as np
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from sklearn.model_selection import StratifiedKFold, cross_val_score
from imblearn.pipeline import Pipeline
from imblearn.over_sampling import SMOTE
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.tree import DecisionTreeClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.neighbors import KNeighborsClassifier
import xgboost as xgb

# --- 1. Load, Clean, and Label Data (Same as before) ---
df = pd.read_csv("dataset8/final_dataset.csv")
tracks = ["Solar8000/HR", "Solar8000/ART_SBP", "Solar8000/ART_DBP",
          "Solar8000/BT", "Solar8000/PLETH_SPO2"]
for col in tracks:
    df = df[df[col] >= 0]
df = df.dropna()
df.columns = ['heart_rate', 'systolic_bp', 'diastolic_bp', 'temperature', 'spo2']
df.drop_duplicates(inplace=True)

scaler = StandardScaler()
X_scaled = scaler.fit_transform(df)
kmeans = KMeans(n_clusters=3, random_state=42, n_init=10)
clusters = kmeans.fit_predict(X_scaled)
silhouette_avg = silhouette_score(X_scaled, clusters)
print(f"The Silhouette Score for the K-Means clustering is: {silhouette_avg:.2f}\n")
df['cluster'] = clusters
centroids = scaler.inverse_transform(kmeans.cluster_centers_)
cluster_centers_df = pd.DataFrame(centroids, columns=df.columns[:-1])
risk_score = cluster_centers_df['heart_rate'] - cluster_centers_df['spo2']
risk_order = risk_score.sort_values().index
label_map = {risk_order[0]: 'Good', risk_order[1]: 'Moderate', risk_order[2]: 'Risk'}
df['health_state'] = df['cluster'].map(label_map)


# --- Correlation Matrix Section (Unchanged as requested) ---
print("\n--- Generating Correlation Matrix ---")
df_corr = df.copy()
numeric_map = {'Good': 0, 'Moderate': 1, 'Risk': 2}
df_corr['health_state_numeric'] = df_corr['health_state'].map(numeric_map)
numeric_cols = ['heart_rate', 'systolic_bp', 'diastolic_bp', 'temperature', 'spo2', 'health_state_numeric']
corr_matrix = df_corr[numeric_cols].corr()

plt.figure(figsize=(10, 8))
sns.heatmap(corr_matrix, annot=True, cmap='coolwarm', fmt=".2f")
plt.title('Correlation Matrix of Vitals and Health State')
plt.savefig('correlation_matrix1.png')
print("Correlation matrix saved as 'correlation_matrix1.png'")


# --- Data and Label Preparation ---
X = df[['heart_rate', 'systolic_bp', 'diastolic_bp', 'temperature', 'spo2']]
y = df['health_state']
le = LabelEncoder()
y_encoded = le.fit_transform(y)

# --- 2. Define Regularized Models and Cross-Validation Strategy ---
models = {
    # C=0.1 applies stronger L2 regularization. A smaller C means a simpler model.
    "Logistic Regression (Regularized)": LogisticRegression(max_iter=1000, C=0.1, solver='liblinear'),

    # min_samples_leaf=10 means a split is only considered if it leaves at least 10 samples
    # in each leaf, preventing the tree from getting too specific.
    "Decision Tree (Regularized)": DecisionTreeClassifier(max_depth=4, min_samples_leaf=10, random_state=42),

    # For KNN, using more neighbors (k) makes the model more robust to outliers and noise.
    # This acts as a form of regularization.
    "K-Nearest Neighbors (Regularized)": KNeighborsClassifier(n_neighbors=10),

    # lambda (L2) and alpha (L1) are explicit regularization terms that penalize large weights.
    # eta (learning_rate) also helps by making the model learn more slowly.
    "XGBoost (Regularized)": xgb.XGBClassifier(objective="multi:softprob", use_label_encoder=False,
                                               eval_metric='mlogloss', random_state=42,
                                               eta=0.1, reg_lambda=1, reg_alpha=0.5)
}

cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)

# --- 3. Run Cross-Validation for Each Regularized Model ---
for name, model in models.items():
    print(f"\n--- Running Cross-Validation for: {name} ---")

    pipeline = Pipeline(steps=[('smote', SMOTE(random_state=42)),
                               ('classifier', model)])

    scores = cross_val_score(pipeline, X, y_encoded, cv=cv, scoring='accuracy')

    print(f"Scores for each fold: {scores}")
    print(f"Average Accuracy: {np.mean(scores):.4f}")
    print(f"Standard Deviation: {np.std(scores):.4f}")