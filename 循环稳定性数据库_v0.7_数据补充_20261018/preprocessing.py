"""Construct preprocessing only when a later authorized experiment needs it.

No fit is executed on import or construction. Pass the returned transformer into
the model pipeline; fit that pipeline only on each training source fold.
"""
def make_preprocessor(feature_names,scale_numeric=False):
    from sklearn.compose import ColumnTransformer
    from sklearn.preprocessing import OneHotEncoder,StandardScaler
    categorical=[f for f in feature_names if f in ('electrolyte','reference_electrode')]
    numeric=[f for f in feature_names if f not in categorical]
    # Integer positions also work with the raw list/NumPy matrices from the API.
    ci=[feature_names.index(f) for f in categorical]
    ni=[feature_names.index(f) for f in numeric]
    return ColumnTransformer([
        ('numeric',StandardScaler() if scale_numeric else 'passthrough',ni),
        ('categorical',OneHotEncoder(handle_unknown='ignore'),ci)],remainder='drop')
