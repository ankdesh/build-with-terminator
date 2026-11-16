"""Deterministic temporary DataFrame operations. Never evaluate model expressions."""
from typing import Any
import json
import pandas as pd


def query_frame(frame: pd.DataFrame, operations: list[dict[str, Any]]) -> pd.DataFrame:
    result = frame.copy(deep=True)
    for operation in operations:
        kind = operation['op']
        column = operation.get('column','')
        columns = operation.get('columns',[])
        groups = operation.get('group_by',[])
        names = [v for v in [column,*columns,*groups] if v]
        missing = sorted(set(names)-set(result.columns))
        if missing: raise ValueError('Unknown columns: '+', '.join(missing))
        if kind == 'filter':
            values = result[column]
            value = json.loads(operation.get('value_json','null'))
            operator = operation.get('operator','eq')
            if operator == 'contains': mask = values.astype('string').str.contains(str(value),regex=False,na=False)
            elif operator == 'is_null': mask = values.isna()
            elif operator == 'not_null': mask = values.notna()
            else:
                functions = {'eq':values.eq,'ne':values.ne,'gt':values.gt,'gte':values.ge,'lt':values.lt,'lte':values.le}
                if operator not in functions: raise ValueError('Unsupported filter operator')
                mask = functions[operator](value)
            result = result.loc[mask.fillna(False)].copy()
        elif kind == 'aggregate':
            metric,alias = operation.get('metric','count'),operation.get('alias','value')
            if metric not in {'count','sum','mean','min','max','median','nunique'}: raise ValueError('Unsupported aggregation')
            if metric != 'count' and not column: raise ValueError('This aggregation requires a column')
            if column and metric in {'sum','mean','median'}:
                result[column] = pd.to_numeric(result[column],errors='raise')
            if groups:
                grouped = result.groupby(groups,dropna=False,observed=True)
                value = grouped[column].agg(metric) if column else grouped.size()
                result = value.rename(alias).reset_index()
            else:
                value = getattr(result[column],metric)() if column else len(result)
                result = pd.DataFrame([{alias:value}])
        elif kind == 'sort': result = result.sort_values(column,ascending=not operation.get('descending',True),kind='stable')
        elif kind == 'limit':
            limit = int(operation.get('limit',20))
            if not 1<=limit<=5000: raise ValueError('Limit must be between 1 and 5000')
            result = result.head(limit).copy()
        elif kind == 'select': result = result[columns].copy()
        elif kind == 'correlation':
            if len(columns)!=2: raise ValueError('Correlation requires two columns')
            values = result[columns].apply(pd.to_numeric,errors='raise').dropna()
            result = pd.DataFrame([{'correlation':values[columns[0]].corr(values[columns[1]]) if len(values)>1 else None,'observations':len(values)}])
        elif kind == 'describe': result = result[columns or list(result.columns)].describe(include='all').reset_index()
        else: raise ValueError('Unsupported query operation: '+kind)
    return result
