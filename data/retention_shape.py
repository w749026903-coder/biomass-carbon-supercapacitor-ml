"""Four user-approved summaries of the same early observation window."""
import numpy as np
FIELDS=('first_half_slope_pp','last_half_slope_pp','quadratic_curvature_pp','peak_relative_time_fraction')
def shape_summaries(points):
 result={k:None for k in FIELDS}
 if len(points)<6:return result
 x=np.array([p['cycle_coordinate']for p in points],dtype=float);y=np.array([p['retention_pct']for p in points],dtype=float);span=float(max(x)-min(x))
 if span<=0:return result
 z=(x-min(x))/span;left=z<=.5;right=z>.5
 if int(left.sum())<3 or int(right.sum())<3:return result
 def slope(x,y):return float(sum((x-x.mean())*(y-y.mean()))/sum((x-x.mean())**2))
 coeff=np.polynomial.polynomial.polyfit(z,y,2)
 return dict(first_half_slope_pp=slope(z[left],y[left]),last_half_slope_pp=slope(z[right],y[right]),quadratic_curvature_pp=float(2*coeff[2]),peak_relative_time_fraction=float(z[np.argmax(y)]))
