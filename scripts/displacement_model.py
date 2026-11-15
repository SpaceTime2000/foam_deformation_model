"""Reduced displacement-controlled foam mechanics, independent of video tracking."""
import numpy as np


def simulate_contact(book_height_mm, fps, tau_s, initial_height_mm=35., rest_height_mm=35.,
                     substeps=8):
    """Quasistatic first-order recovery with unilateral prescribed plate contact."""
    plate=np.asarray(book_height_mm,dtype=float)
    if plate.ndim!=1 or not len(plate) or np.any(np.isnan(plate)) or np.any(plate<=0):
        raise ValueError('Book heights must be a nonempty positive vector; infinity means no plate.')
    if not np.isfinite(fps) or fps<=0 or not np.isfinite(tau_s) or tau_s<=0:
        raise ValueError('FPS and recovery time must be positive.')
    if not np.isfinite(rest_height_mm) or not 0<initial_height_mm<=rest_height_mm or type(substeps) is not int or substeps<1:
        raise ValueError('Invalid initial height or substep count.')
    heights=np.empty(len(plate));contact=np.zeros(len(plate),dtype=bool)
    heights[0]=min(initial_height_mm,plate[0])
    contact[0]=plate[0]<=initial_height_mm
    decay=np.exp(-1/(fps*substeps*tau_s))
    for index in range(1,len(plate)):
        height=heights[index-1]
        # An absent plate has no influence above the resting object.
        p0=min(plate[index-1],rest_height_mm*3)
        p1=min(plate[index],rest_height_mm*3)
        for step in range(1,substeps+1):
            ceiling=p0+(p1-p0)*step/substeps
            free=rest_height_mm-(rest_height_mm-height)*decay
            active=ceiling<=free
            height=min(free,ceiling)
        heights[index]=height
        contact[index]=active
    return heights,contact


def project_markers(reference_xy, height_mm, table_y_px, rest_height_mm=35.):
    """Uniform vertical strain maps reference material markers into the camera."""
    points=np.asarray(reference_xy,dtype=float)
    height=np.asarray(height_mm,dtype=float)
    result=np.broadcast_to(points,(len(np.atleast_1d(height)),*points.shape)).copy()
    result[:,:,1]=table_y_px+(points[None,:,1]-table_y_px)*np.atleast_1d(height)[:,None]/rest_height_mm
    return result


def marker_height(reference_xy, observed_xy, table_y_px, rest_height_mm=35.):
    """Robust affine vertical strain estimate; translation is diagnosed separately."""
    reference=np.asarray(reference_xy,dtype=float)
    observed=np.asarray(observed_xy,dtype=float)
    valid=np.isfinite(observed).all(axis=1)&np.isfinite(reference).all(axis=1)
    if valid.sum()<4:
        return np.nan,np.nan,np.nan
    y0=reference[valid,1]; y=observed[valid,1]
    if np.ptp(y0)<30:
        return np.nan,np.nan,np.nan
    slopes=[]
    for i in range(len(y0)):
        for j in range(i+1,len(y0)):
            if abs(y0[j]-y0[i])>=30:
                slopes.append((y[j]-y[i])/(y0[j]-y0[i]))
    if not slopes:
        return np.nan,np.nan,np.nan
    scale=float(np.median(slopes))
    translation=float(np.median(y-scale*y0))
    residual=float(np.sqrt(np.mean((y-(translation+scale*y0))**2)))
    base_shift=translation-(1-scale)*table_y_px
    return rest_height_mm*scale,base_shift,residual


def complete_book_input(values,frame_numbers,rest_height_mm,max_gap=0):
    """Explicit bounded input reconstruction. Raw observations remain separate."""
    raw=np.asarray(values,dtype=float)
    completed=raw.copy()
    estimated=np.zeros(len(raw),dtype=bool)
    repairs=[]
    missing=np.isnan(raw)
    beginnings=np.flatnonzero(missing & ~np.r_[False,missing[:-1]])
    endings=np.flatnonzero(missing & ~np.r_[missing[1:],False])
    for first,last in zip(beginnings,endings):
        count=last-first+1
        if count>max_gap or first==0 or last==len(raw)-1:
            raise ValueError(f'Book input missing at frames {frame_numbers[first]}-{frame_numbers[last]}. '
                             f'Allow a bounded reconstruction with --max-book-gap {count}, or correct the book observations.')
        left,right=first-1,last+1
        p0,p1=raw[left],raw[right]
        if np.isfinite(p0) and np.isfinite(p1):
            completed[first:last+1]=np.linspace(p0,p1,count+2)[1:-1]
            method='linear interpolation between observed book heights'
        elif np.isposinf(p0) and np.isposinf(p1):
            completed[first:last+1]=np.inf
            method='unconstrained plate bracketed by absent-book observations'
        elif np.isfinite(p0) and np.isposinf(p1):
            previous=np.flatnonzero(np.isfinite(raw[:left]))
            if not len(previous) or left-previous[-1]>max_gap+1:
                raise ValueError('Cannot estimate upward book velocity before missing input.')
            previous=int(previous[-1])
            velocity=(raw[left]-raw[previous])/(left-previous)
            end_prediction=p0+velocity*(right-left)
            if velocity<=0 or end_prediction<rest_height_mm:
                raise ValueError('Book exit is inconsistent with an upward constant-velocity reconstruction. Manual book input is required.')
            completed[first:last+1]=p0+velocity*np.arange(1,count+1)
            method='constant upward velocity from preceding observed book heights'
        else:
            raise ValueError('Book-entry gap has insufficient motion information. Correct the book observations.')
        estimated[first:last+1]=True
        repairs.append(dict(first_frame=int(frame_numbers[first]),last_frame=int(frame_numbers[last]),
                            count=int(count),method=method))
    return completed,estimated,repairs
