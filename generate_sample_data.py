import pandas as pd
import numpy as np

# Generate sample SPC-like data
np.random.seed(42)
n = 200

dates = pd.date_range('2025-01-01', periods=n, freq='D')
lots = [f"LOT-{i+1:04d}" for i in range(n)]

# Simulate 3 measurement columns
data = {
    'LotNo': lots,
    '製造日期': dates,
    'Thickness': np.random.normal(1.008, 0.015, n).round(4),
    'Width': np.random.normal(25.00, 0.30, n).round(3),
    'Weight': np.random.normal(150.0, 2.0, n).round(2),
    'Temperature': np.random.normal(23.0, 0.5, n).round(1),
    'Humidity': np.random.normal(45.0, 3.0, n).round(1),
    'Category': np.random.choice(['A', 'B', 'C'], n),
}

# Add some UCL/LCL columns
data['Thickness_UCL'] = [1.05] * n
data['Thickness_LCL'] = [0.97] * n
data['Width_UCL'] = [26.0] * n
data['Width_LCL'] = [24.0] * n

# Add some outliers
data['Thickness'][10] = 1.06   # Over UCL
data['Thickness'][50] = 0.96   # Under LCL
data['Width'][30] = 26.5       # Over UCL

df = pd.DataFrame(data)
df.to_csv('sample_data/demo_spc_data.csv', index=False, encoding='utf-8-sig')
print(f"Generated {len(df)} rows -> sample_data/demo_spc_data.csv")
print(df.head())
