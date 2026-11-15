"""Independent book segmentation and ink-dot observations for marked foam."""
import cv2
import numpy as np
from scipy.optimize import linear_sum_assignment


def detect_book(frame, x_range, table_y):
    """Fit the lower maroon-cover boundary; binding offset is calibrated separately."""
    left,right=map(int,x_range)
    columns=np.linspace(left,right,45).astype(int)
    blue,green,red=cv2.split(frame.astype(np.float32))
    mask=(red>40)&(red-green>12)&(red>1.25*green)&(red>1.15*blue)
    xs=[];ys=[]
    for x in columns:
        rows=np.flatnonzero(mask[:max(1,int(table_y)-8),max(0,x-2):x+3].mean(axis=1)>.6)
        if len(rows):
            xs.append(x);ys.append(rows[-1])
    if len(xs)<len(columns)*.7:
        return np.inf,0.,len(xs)/len(columns)
    xs=np.asarray(xs);ys=np.asarray(ys)
    fit=np.polyfit(xs,ys,1)
    residual=ys-np.polyval(fit,xs)
    valid=np.abs(residual-np.median(residual))<=max(4,3*np.median(np.abs(residual)))
    if valid.sum()<20:
        return np.nan,np.nan,len(xs)/len(columns)
    fit=np.polyfit(xs[valid],ys[valid],1)
    return float(np.polyval(fit,np.mean(x_range))),float(np.degrees(np.arctan(fit[0]))),len(xs)/len(columns)


def detect_dots(frame, roi):
    left,top,right,bottom=map(int,roi)
    crop=frame[top:bottom,left:right]
    gray=cv2.cvtColor(crop,cv2.COLOR_BGR2GRAY)
    dark=cv2.morphologyEx(gray,cv2.MORPH_BLACKHAT,cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(17,17)))
    binary=(dark>=12).astype(np.uint8)
    count,labels,stats,centers=cv2.connectedComponentsWithStats(binary)
    dots=[]
    for index in range(1,count):
        x,y,w,h,area=stats[index]
        if not 10<=area<=600 or w>35 or h>35:
            continue
        cx,cy=centers[index]
        px=int(cx);py=int(cy)
        patch=crop[max(0,py-8):py+9,max(0,px-8):px+9]
        b,g,r=np.median(patch.reshape(-1,3).astype(float),axis=0)
        if g-b<8 or g<.8*r:
            continue
        dots.append([cx+left,cy+top])
    return np.asarray(dots,dtype=float).reshape(-1,2)


def assign_dots(reference,candidates,table_y,previous_scale=1.,previous_shift=(0.,0.)):
    """Match visible ink blobs to reference material points, with outlier rejection."""
    reference=np.asarray(reference,dtype=float)
    missing=np.full_like(reference,np.nan)
    if len(candidates)<4:
        return missing,previous_scale,previous_shift
    best=None
    # Global scale hypotheses permit reacquisition after compression/occlusion.
    scales=np.unique(np.r_[previous_scale,np.clip(previous_scale+np.array([-.1,-.05,.05,.1]),.05,1.3),
                           np.linspace(.1,1.15,15)])
    for scale in scales:
        predicted=reference.copy()
        predicted[:,0]+=previous_shift[0]
        predicted[:,1]=table_y+scale*(reference[:,1]-table_y)+previous_shift[1]
        dx=predicted[:,None,0]-candidates[None,:,0]
        dy=predicted[:,None,1]-candidates[None,:,1]
        cost=(dx/15)**2+(dy/28)**2
        # Explicit unmatched assignments avoid forcing identities onto background.
        augmented=np.c_[cost,np.full((len(reference),len(reference)),4.)]
        rows,cols=linear_sum_assignment(augmented)
        good=(cols<len(candidates))
        rows=rows[good];cols=cols[good]
        good=cost[rows,cols]<4
        rows=rows[good];cols=cols[good]
        if len(rows)<4:
            continue
        y0=reference[rows,1];y=candidates[cols,1]
        if np.ptp(y0)<40:
            continue
        fit=np.polyfit(y0,y,1)
        residual=np.abs(y-np.polyval(fit,y0))
        valid=residual<=max(4,3*np.median(residual))
        if valid.sum()<4 or not .03<fit[0]<1.3:
            continue
        score=int(valid.sum())-float(np.mean(residual[valid]))/10-float(np.mean(cost[rows[valid],cols[valid]]))/20
        if best is None or score>best[0]:
            observed=missing.copy()
            observed[rows[valid]]=candidates[cols[valid]]
            shift=(float(np.median(observed[rows[valid],0]-reference[rows[valid],0])),
                   float(fit[1]-(1-fit[0])*table_y))
            best=(score,observed,float(fit[0]),shift)
    return (missing,previous_scale,previous_shift) if best is None else best[1:]


def snap_markers(frame,points,roi):
    candidates=detect_dots(frame,roi)
    snapped=[]
    for point in points:
        if not len(candidates):
            raise ValueError('No ink dots detected. Choose sharper/larger marks or another resting frame.')
        distances=np.linalg.norm(candidates-point,axis=1)
        index=int(np.argmin(distances))
        if distances[index]>14:
            raise ValueError(f'Click {point} is not near a detected ink dot.')
        snapped.append(candidates[index])
    result=np.asarray(snapped)
    if len(np.unique(np.round(result,1),axis=0))!=len(result):
        raise ValueError('Two clicks selected the same marker.')
    return result


def track_marker_step(previous,current,previous_points,reference,candidates,table_y):
    """Keep marker identities through adjacent-frame optical flow and ink support."""
    result=np.full_like(reference,np.nan,dtype=float)
    known=np.flatnonzero(np.isfinite(previous_points).all(axis=1))
    if len(known):
        def normalized(frame):
            gray=cv2.cvtColor(frame,cv2.COLOR_BGR2GRAY)
            return cv2.addWeighted(gray,1,cv2.GaussianBlur(gray,(0,0),5),-1,128)
        a=normalized(previous);b=normalized(current)
        points=previous_points[known].astype(np.float32).reshape(-1,1,2)
        options=dict(winSize=(21,21),maxLevel=3,
                     criteria=(cv2.TERM_CRITERIA_EPS|cv2.TERM_CRITERIA_COUNT,40,.01))
        moved,status,_=cv2.calcOpticalFlowPyrLK(a,b,points,None,**options)
        if moved is not None:
            back,reverse,_=cv2.calcOpticalFlowPyrLK(b,a,moved,None,**options)
            if back is not None:
                valid=(status.ravel()>0)&(reverse.ravel()>0)&(np.linalg.norm(back-points,axis=2).ravel()<2)
                used=set()
                for local_index in np.flatnonzero(valid):
                    point=moved[local_index,0]
                    if not len(candidates):
                        continue
                    distances=np.linalg.norm(candidates-point,axis=1)
                    nearest=int(np.argmin(distances))
                    if distances[nearest]<=10 and nearest not in used:
                        result[known[local_index]]=candidates[nearest]
                        used.add(nearest)
    # Reacquire missing dots only from the motion of surviving material dots.
    good=np.isfinite(result).all(axis=1)
    if good.sum()>=4 and np.ptp(reference[good,1])>=50:
        fit=np.polyfit(reference[good,1],result[good,1],1)
        x_shift=float(np.median(result[good,0]-reference[good,0]))
        for index in np.flatnonzero(~good):
            predicted=np.array([reference[index,0]+x_shift,np.polyval(fit,reference[index,1])])
            if not len(candidates):continue
            distances=np.linalg.norm(candidates-predicted,axis=1)
            nearest=int(np.argmin(distances))
            already=np.isfinite(result).all(axis=1)
            if distances[nearest]<=8 and not np.any(np.linalg.norm(result[already]-candidates[nearest],axis=1)<2):
                result[index]=candidates[nearest]
    return result


def initialize_markers(reference_frame,current_frame,reference,roi):
    """Locate a resting dot constellation despite between-press translation."""
    points=np.asarray(reference,dtype=float)
    height,width=current_frame.shape[:2]
    expanded=[max(0,int(roi[0]-250)),max(0,int(roi[1]-120)),
              min(width,int(roi[2]+250)),min(height,int(roi[3]+30))]
    candidates=detect_dots(current_frame,expanded)
    missing=np.full_like(points,np.nan)
    if len(candidates)<4:
        return missing,0.,expanded
    differences=(candidates[None,:,:]-points[:,None,:]).reshape(-1,2)
    allowed=(abs(differences[:,0])<=240)&(abs(differences[:,1])<=100)
    shifts=np.unique(np.round(differences[allowed]/4)*4,axis=0)
    best=None
    for shift in shifts:
        expected=points+shift
        costs=np.linalg.norm(expected[:,None,:]-candidates[None,:,:],axis=2)
        rows,cols=linear_sum_assignment(np.c_[costs,np.full((len(points),len(points)),15.)])
        keep=cols<len(candidates)
        rows=rows[keep];cols=cols[keep]
        keep=costs[rows,cols]<15
        rows=rows[keep];cols=cols[keep]
        if len(rows)<4 or np.ptp(points[rows,1])<50:
            continue
        offsets=candidates[cols]-points[rows]
        center=np.median(offsets,axis=0)
        errors=np.linalg.norm(offsets-center,axis=1)
        good=errors<12
        score=int(good.sum())-float(np.mean(errors[good]))/20 if good.any() else -1
        if best is None or score>best[0]:
            observed=missing.copy()
            observed[rows[good]]=candidates[cols[good]]
            best=(score,observed)
    if best is None:
        return missing,0.,expanded
    observed=best[1]
    # Refine a translation match with independent image-axis scales. This
    # accommodates view/pose changes without assigning identities by proximity alone.
    for _ in range(3):
        known=np.isfinite(observed).all(axis=1)
        if known.sum()<4 or np.ptp(points[known,0])<150 or np.ptp(points[known,1])<50:
            break
        x_fit=np.polyfit(points[known,0],observed[known,0],1)
        y_fit=np.polyfit(points[known,1],observed[known,1],1)
        if not .7<x_fit[0]<1.3 or not .7<y_fit[0]<1.3:
            break
        predicted=np.c_[np.polyval(x_fit,points[:,0]),np.polyval(y_fit,points[:,1])]
        costs=np.linalg.norm(predicted[:,None,:]-candidates[None,:,:],axis=2)
        rows,cols=linear_sum_assignment(np.c_[costs,np.full((len(points),len(points)),15.)])
        updated=missing.copy()
        for row,column in zip(rows,cols):
            if column<len(candidates) and costs[row,column]<15:
                updated[row]=candidates[column]
        if np.isfinite(updated).all(axis=1).sum()<known.sum():
            break
        observed=updated
    return observed,float(np.isfinite(observed).all(axis=1).mean()),expanded


def refine_book_edge(frame,color_y,angle,offset,x_range):
    """Use cover segmentation as a search prior for the visible underside edge."""
    from scipy.ndimage import gaussian_filter1d
    if not np.isfinite(color_y):
        return color_y,angle,0.
    columns=np.linspace(x_range[0],x_range[1],30).astype(int)
    center=float(np.mean(x_range))
    xs=[];ys=[];qualities=[]
    for x in columns:
        expected=color_y+offset+np.tan(np.radians(angle))*(x-center)
        lower=max(0,int(expected-80));upper=min(frame.shape[0]-1,int(expected+80))
        if upper-lower<8:continue
        profile=np.mean(frame[lower:upper,max(0,x-2):x+3,1].astype(float),axis=1)
        gradient=np.gradient(gaussian_filter1d(profile,1.5))
        index=int(np.argmax(gradient))
        if gradient[index]<2:continue
        xs.append(x);ys.append(lower+index);qualities.append(gradient[index])
    if len(xs)<15:return np.nan,np.nan,0.
    xs=np.asarray(xs);ys=np.asarray(ys)
    fit=np.polyfit(xs,ys,1)
    residual=abs(ys-np.polyval(fit,xs))
    good=residual<=max(4,3*np.median(residual))
    if good.sum()<15:return np.nan,np.nan,0.
    fit=np.polyfit(xs[good],ys[good],1)
    return float(np.polyval(fit,center)),float(np.degrees(np.arctan(fit[0]))),float(np.median(np.asarray(qualities)[good]))


def reacquire_resting_constellation(frame,reference,roi,survivors):
    """Reacquire a near-rest dot pattern after severe-compression tracking loss."""
    points,quality,_=initialize_markers(frame,frame,reference,roi)
    good=np.isfinite(points).all(axis=1)&np.isfinite(reference).all(axis=1)
    if good.sum()<6 or np.ptp(reference[good,1])<50:
        return None
    fit=np.polyfit(reference[good,1],points[good,1],1)
    residual=points[good,1]-np.polyval(fit,reference[good,1])
    if not .85<=fit[0]<=1.15 or np.sqrt(np.mean(residual**2))>5:
        return None
    shared=good&np.isfinite(survivors).all(axis=1)
    if shared.any() and np.median(np.linalg.norm(points[shared]-survivors[shared],axis=1))>12:
        return None
    return points
