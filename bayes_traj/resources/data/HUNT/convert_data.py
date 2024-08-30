import pandas as pd

def convert_to_csv(filepath):

    df = pd.read_stata(filepath, columns=['PID_109925', 'Sex',
                                          'PartAg_YH1BLQ', 'PartAg_YH2BLQ', 'PartAg_YH3BLQ', 'PartAg_NT3BLQ1', 'PartAg_NT4BLQ1',
                                          'SmoPackYrs_NT3BLQ1', 'SmoPackYrs_NT4BLQ1',
                                          'FEV1ZSGLI_YH1LuM', 'FEV1ZSGLI_YH2LuM', 'FEV1ZSGLI_YH3LuM', 'FEV1ZSGLI_NT3LuM', 'FEV1ZSGLI_NT4LuM'])

    df.columns = df.columns.str.replace('YH1BLQ', 'YH1').str.replace('YH2BLQ', 'YH2') \
        .str.replace('YH3BLQ', 'YH3').str.replace('NT3BLQ1', 'NT3') \
        .str.replace('NT4BLQ1', 'NT4').str.replace('YH1LuM', 'YH1') \
        .str.replace('YH2LuM', 'YH2').str.replace('YH3LuM', 'YH3') \
        .str.replace('NT3LuM', 'NT3').str.replace('NT4LuM', 'NT4')

    # Convert the DataFrame from wide to long format
    long_df = pd.wide_to_long(df,
                              stubnames=['PartAg', 'SmoPackYrs', 'FEV1ZSGLI'],
                              i='PID_109925',
                              j='TimePoint',
                              sep='_',
                              suffix='.+')

    long_df = long_df.dropna(subset=['PartAg', 'SmoPackYrs', 'FEV1ZSGLI'], how='all') # Filter out rows with no data

    long_df['Intercept'] = 1.0 # add intercept column filled with 1s

    long_df = long_df.sort_values(by=['PID_109925', 'TimePoint'])
    long_df = long_df.reset_index()

    long_df['Sex'] = long_df['Sex'].replace({'Kvinne': 0, 'Mann': 1}) # replace sex with 0 and 1

    count_missing_fev1zs = long_df['FEV1ZSGLI'].isna().sum()
    count_missing_partag = long_df['PartAg'].isna().sum()
    count_missing_smopackyrs = long_df['SmoPackYrs'].isna().sum()

    print(f"Number of rows without FEV1ZSGLI: {count_missing_fev1zs}")
    print(f"Number of rows without PartAg: {count_missing_partag}")
    print(f"Number of rows without SmoPackYrs: {count_missing_smopackyrs}")

    print(long_df.head(10))

    long_df.to_csv('trajectory_data.csv', index=True)

convert_to_csv('/Users/miarodde/Documents/Phd/Bayesian/Data/lung_function_cohort.dta')