"""Book-driven foam identification. Run setup, track, fit, then preview."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import cv2
import numpy as np
from scipy.optimize import minimize_scalar
from displacement_model import simulate_contact,project_markers,marker_height,complete_book_input
from displacement_tracking import detect_book,detect_dots,assign_dots,track_marker_step,initialize_markers,refine_book_edge,reacquire_resting_constellation

PROJECT=Path(__file__).resolve().parent.parent
DEFAULT_VIDEO=PROJECT/'data'/'train'/'marked_foam_train.mp4'
DEFAULT_CONFIG=PROJECT/'data'/'annotations'/'marked_foam_train.json'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def paths(config_path):
    stem=config_path.stem
    processed=PROJECT/'data'/'processed'/'displacement'/stem
    visuals=PROJECT/'visualizations'/'displacement'/stem
    return processed,visuals


def load_config(path):
    config=json.loads(path.read_text())
    video=Path(config['video'])
    if video.stat().st_size!=config['video_size_bytes'] or video.stat().st_mtime_ns!=config['video_modified_ns']:
        raise ValueError('Input video changed since setup. Review and save setup again.')
    return config,video


def track(config_path):
    config,video=load_config(config_path)
    processed,_=paths(config_path);processed.mkdir(parents=True,exist_ok=True)
    reference=np.asarray(config['markers'],dtype=float)
    table=config['table_y_px'];rest=config['dimensions_mm'][2]
    px_per_mm=(table-config['rest_top_y_px'])/rest
    frames=[];trial_ids=[];observed=[];plate=[];angles=[];coverage=[];height=[];shifts=[];scatter=[]
    reference_rows=[];table_rows=[];scale_rows=[]
    capture=cv2.VideoCapture(str(video))
    capture.set(cv2.CAP_PROP_POS_FRAMES,config['book_reference_frame'])
    ok,book_reference=capture.read()
    if not ok:raise ValueError('Cannot read book reference.')
    raw_reference,reference_angle,_=detect_book(book_reference,config['book_x_range'],config['table_y_px'])
    refined_reference,_,_=refine_book_edge(book_reference,raw_reference,reference_angle,
                                          config['book_binding_offset_px'],config['book_x_range'])
    if not np.isfinite(refined_reference):
        raise ValueError('Book edge refinement failed at reference. Choose a clearer book reference frame.')
    edge_phase_offset=float(np.mean(np.asarray(config['book_points'])[:,1])-refined_reference)
    capture.set(cv2.CAP_PROP_POS_FRAMES,config['reference_frame'])
    ok,reference_frame=capture.read()
    if not ok:raise ValueError('Cannot read resting reference.')
    for trial_id,trial in enumerate(config['trials'],1):
        capture.set(cv2.CAP_PROP_POS_FRAMES,trial['start'])
        previous_frame=None;previous_points=None
        trial_reference=None
        for index in range(trial['start'],trial['stop']+1):
            ok,frame=capture.read()
            if not ok:
                capture.release();raise ValueError(f'Cannot decode frame {index}')
            if previous_frame is None:
                points,initial_quality,active_roi=initialize_markers(reference_frame,frame,reference,config['marker_roi'])
                known=np.isfinite(points).all(axis=1)
                if known.sum()<4 or np.ptp(reference[known,1])<50:
                    raise ValueError(f'Press {trial_id}: resting dot identities are unclear. Choose a clearer resting start frame.')
                pose=np.polyfit(reference[known,1],points[known,1],1)
                if not .7<pose[0]<1.3:
                    raise ValueError(f'Press {trial_id}: initial marker geometry is inconsistent with rest.')
                table=float(np.polyval(pose,config['table_y_px']))
                top=float(np.polyval(pose,config['rest_top_y_px']))
                px_per_mm=(table-top)/rest
                trial_reference=points.copy()
                motion_reference=reference.copy()
                horizontal_pose=np.polyfit(reference[known,0],points[known,0],1)
                motion_reference[:,0]=np.polyval(horizontal_pose,reference[:,0])
                motion_reference[:,1]=np.polyval(pose,reference[:,1])
                motion_reference[known]=points[known]
                candidates=detect_dots(frame,active_roi)
            else:
                candidates=detect_dots(frame,active_roi)
                points=track_marker_step(previous_frame,frame,previous_points,motion_reference,candidates,table)
                if np.isfinite(points).all(axis=1).sum()<4:
                    reacquired=reacquire_resting_constellation(frame,motion_reference,active_roi,points)
                    if reacquired is not None:
                        points=reacquired
            previous_frame=frame
            previous_points=points
            h,base_shift,residual=marker_height(trial_reference,points,table,rest)
            book_y,angle,cover=detect_book(frame,config['book_x_range'],table)
            book_y,angle,edge_quality=refine_book_edge(frame,book_y,angle,config['book_binding_offset_px'],config['book_x_range'])
            book_height=(table-book_y-edge_phase_offset)/px_per_mm if np.isfinite(book_y) else book_y
            if np.isfinite(book_height) and book_height<=0:
                book_height=np.nan
            frames.append(index);trial_ids.append(trial_id);observed.append(points)
            plate.append(book_height);angles.append(angle);coverage.append(cover)
            height.append(h);shifts.append(base_shift/px_per_mm);scatter.append(residual/px_per_mm)
            reference_rows.append(trial_reference);table_rows.append(table);scale_rows.append(px_per_mm)
        print(f'Tracked press {trial_id}: frames {trial["start"]}-{trial["stop"]}.',flush=True)
    capture.release()
    np.savez_compressed(processed/'observations.npz',frames=frames,trial_ids=trial_ids,
                        markers=observed,book_height_mm=plate,book_angle_deg=angles,
                        book_coverage=coverage,measured_height_mm=height,
                        base_shift_mm=shifts,marker_scatter_mm=scatter,reference_xy=reference_rows,
                        calibrated_table_y_px=table_rows,calibrated_px_per_mm=scale_rows)
    (processed/'tracking_metadata.json').write_text(json.dumps(dict(config_hash=digest(config_path),
        method='Per-trial resting marker initialization, persistent ink-supported flow, maroon-cover prior and refined underside edge',
        observation_assumption='Approximately uniform vertical strain, stationary camera and table',
        config=config),indent=2))
    with (processed/'observations.csv').open('w',newline='') as handle:
        writer=csv.writer(handle);writer.writerow(['frame','trial','book_height_mm','marker_height_mm',
                                                   'marker_count','base_shift_mm','marker_scatter_mm'])
        for values in zip(frames,trial_ids,plate,height,observed,shifts,scatter):
            f,t,b,h,pts,offset,error=values
            writer.writerow([f,t,b,h,int(np.isfinite(pts).all(axis=1).sum()),offset,error])
    observed_array=np.asarray(observed)
    frame_trials=np.asarray(trial_ids)
    report=[]
    for trial_id in range(1,len(config['trials'])+1):
        counts=np.isfinite(observed_array[frame_trials==trial_id]).all(axis=2).sum(axis=1)
        entry=dict(trial=trial_id,frames=int(len(counts)),
                   frames_with_four_markers=int(np.sum(counts>=4)),
                   full_marker_frames=int(np.sum(counts==len(reference))))
        report.append(entry)
        print(f"Press {trial_id}: {entry['frames_with_four_markers']}/{entry['frames']} frames have at least four material markers.",flush=True)
    (processed/'tracking_quality.json').write_text(json.dumps(report,indent=2))
    print('Saved',processed/'observations.npz')
    print('Inspect tracking with: python displacement.py preview --config',config_path,'--tracking-only')


def load_observations(config_path):
    config,video=load_config(config_path)
    processed,visuals=paths(config_path)
    metadata=json.loads((processed/'tracking_metadata.json').read_text())
    if metadata['config_hash']!=digest(config_path):
        raise ValueError('Setup changed. Run the track command again.')
    with np.load(processed/'observations.npz') as archive:
        observations={name:archive[name] for name in archive.files}
    if 'reference_xy' not in observations:
        raise ValueError('Tracking initialization was updated. Run the track command again.')
    return config,video,processed,visuals,observations


def prepare_trials(config,observations,max_book_gap=0):
    reference=np.asarray(config['markers'],dtype=float)
    rest=config['dimensions_mm'][2];table=config['table_y_px']
    px_per_mm=(table-config['rest_top_y_px'])/rest
    trials=[]
    for trial_id,annotation in enumerate(config['trials'],1):
        mask=observations['trial_ids']==trial_id
        trial={key:value[mask] for key,value in observations.items()}
        trial.update(id=trial_id,role=annotation['role'])
        if len(trial['frames'])<15:
            raise ValueError(f'Press {trial_id}: interval is too short.')
        try:
            filled,estimated,repairs=complete_book_input(trial['book_height_mm'],trial['frames'],
                                                       rest,max_book_gap)
        except ValueError as error:
            raise ValueError(f'Press {trial_id}: {error}') from error
        trial['book_height_mm']=filled
        trial['book_input_estimated']=estimated
        trial['book_input_repairs']=repairs
        if not np.any(np.isfinite(trial['book_height_mm']) & (trial['book_height_mm']<.95*rest)):
            raise ValueError(f'Press {trial_id}: no pressing book trajectory detected. Review calibration.')
        trial['reference']=trial['reference_xy'][0]
        trial['table_y']=float(trial['calibrated_table_y_px'][0])
        trial['px_per_mm']=float(trial['calibrated_px_per_mm'][0])
        observed=trial['markers']
        valid=np.isfinite(observed[:,:,1]) & np.isfinite(trial['reference'][None,:,1])
        complete=valid.sum(axis=1)>=4
        valid &= complete[:,None]
        if valid.sum()<40 or complete.sum()<10:
            raise ValueError(f'Press {trial_id}: insufficient marker observations. Review tracking before fitting.')
        first=trial['measured_height_mm'][0]
        if not np.isfinite(first) or not .9*rest<=first<=1.1*rest:
            raise ValueError(f'Press {trial_id}: start must show resting foam with visible markers.')
        # Initial state is known rest; no later foam observations drive simulation.
        trial['initial_height_mm']=rest
        trial['valid_marker_mask']=valid
        trials.append(trial)
    return trials


def predict(trial,config,tau,substeps=8):
    heights,contact=simulate_contact(trial['book_height_mm'],config['capture_fps'],tau,
                                    trial['initial_height_mm'],config['dimensions_mm'][2],substeps)
    markers=project_markers(trial['reference'],heights,trial.get('table_y',config['table_y_px']),config['dimensions_mm'][2])
    return heights,contact,markers


def loss(trials,config,tau):
    errors=[]
    for trial in trials:
        _,_,predicted=predict(trial,config,tau)
        error=(predicted[:,:,1]-trial['markers'][:,:,1])/trial['px_per_mm']
        errors.append(float(np.mean(error[trial['valid_marker_mask']]**2)))
    return float(np.mean(errors))


def estimate(trials,config):
    lower=1/config['capture_fps'];upper=2.
    result=minimize_scalar(lambda log_tau:loss(trials,config,np.exp(log_tau)),
                          bounds=(np.log(lower),np.log(upper)),method='bounded')
    if not result.success:raise RuntimeError(result.message)
    return float(np.exp(result.x))


def evaluate_trials(trials,config,tau):
    results=[]
    for trial in trials:
        heights,contact,markers=predict(trial,config,tau)
        valid=trial['valid_marker_mask']
        error=(markers[:,:,1]-trial['markers'][:,:,1])/trial['px_per_mm']
        identity=project_markers(trial['reference'],np.full(len(heights),config['dimensions_mm'][2]),
                                 trial.get('table_y',config['table_y_px']),config['dimensions_mm'][2])
        identity_error=(identity[:,:,1]-trial['markers'][:,:,1])/trial['px_per_mm']
        instant_height=np.minimum(config['dimensions_mm'][2],trial['book_height_mm'])
        instant=project_markers(trial['reference'],instant_height,trial['table_y'],config['dimensions_mm'][2])
        instant_error=(instant[:,:,1]-trial['markers'][:,:,1])/trial['px_per_mm']
        # Gap is determined from observed marker strain and prescribed book, not fitted contact state.
        gap=(trial['book_height_mm']>trial['measured_height_mm']+1.)
        recovery=gap & (trial['measured_height_mm']<config['dimensions_mm'][2]-.3)
        recovery_mask=valid & recovery[:,None]
        results.append(dict(trial=trial['id'],role=trial['role'],
            marker_rmse_mm=float(np.sqrt(np.mean(error[valid]**2))),
            rest_baseline_marker_rmse_mm=float(np.sqrt(np.mean(identity_error[valid]**2))),
            instantaneous_baseline_marker_rmse_mm=float(np.sqrt(np.mean(instant_error[valid]**2))),
            instantaneous_baseline_recovery_rmse_mm=float(np.sqrt(np.mean(instant_error[recovery_mask]**2))) if recovery_mask.any() else None,
            recovery_marker_rmse_mm=float(np.sqrt(np.mean(error[recovery_mask]**2))) if recovery_mask.any() else None,
            recovery_frames=int(recovery.sum()),marker_frame_coverage=float((valid.sum(axis=1)>=4).mean()),
            base_shift_rms_mm=float(np.sqrt(np.nanmean(trial['base_shift_mm']**2))),
            maximum_book_tilt_deg=float(np.nanmax(abs(trial['book_angle_deg']))),
            horizontal_marker_rmse_mm=float(np.sqrt(np.nanmean(((trial['markers'][:,:,0]-trial['reference'][None,:,0])/trial['px_per_mm'])**2))),
            marker_height_rmse_mm=float(np.sqrt(np.nanmean((heights-trial['measured_height_mm'])**2)))))
    return results


def fit(config_path,max_book_gap=0):
    config,video,processed,visuals,observations=load_observations(config_path)
    trials=prepare_trials(config,observations,max_book_gap)
    repairs=[dict(trial=trial['id'],intervals=trial['book_input_repairs']) for trial in trials if trial['book_input_repairs']]
    if repairs:
        print('ESTIMATED BOOK INPUT (raw observations retained):',json.dumps(repairs),flush=True)
    training=[trial for trial in trials if trial['role']=='train']
    if len(training)<2:
        raise ValueError('Use at least two complete training presses and preferably a separate validation press.')
    tau=estimate(training,config)
    folds=[]
    for index,validation in enumerate(training):
        fitted=estimate([trial for j,trial in enumerate(training) if j!=index],config)
        folds.append(dict(validation_trial=validation['id'],tau_s=fitted,
                          marker_mse_mm2=loss([validation],config,fitted)))
    results=evaluate_trials(trials,config,tau)
    best_loss=loss(training,config,tau)
    half_loss=loss(training,config,max(1/config['capture_fps'],tau/2))
    twice_loss=loss(training,config,min(2.,tau*2))
    weak_identification=(min(half_loss,twice_loss)<=best_loss*1.05)
    profile_grid=np.geomspace(1/config['capture_fps'],2,50)
    profile=dict(tau_s=profile_grid.tolist(),training_marker_mse_mm2=[loss(training,config,value) for value in profile_grid])
    (processed/'identifiability.json').write_text(json.dumps(profile,indent=2))
    convergence=[]
    for trial in trials:
        coarse,_,_=predict(trial,config,tau,8);fine,_,_=predict(trial,config,tau,16)
        convergence.append(float(np.max(abs(coarse-fine))))
    parameters=dict(model='displacement-controlled first-order contact recovery',
        dimensions_mm=config['dimensions_mm'],recovery_time_s=tau,capture_fps=config['capture_fps'],
        training_trials=[trial['id'] for trial in training],cross_validation=folds,
        max_book_gap=max_book_gap,book_input_repairs=repairs,
        config_hash=digest(config_path),observations_hash=digest(processed/'observations.npz'),
        fit_at_boundary=bool(tau<1.05/config['capture_fps'] or tau>1.9),
        max_substep_difference_mm=max(convergence),
        weak_time_constant_identification=bool(weak_identification),
        training_marker_mse_mm2=best_loss,
        half_tau_marker_mse_mm2=half_loss,twice_tau_marker_mse_mm2=twice_loss,
        equation='h_free=H-(H-h)*exp(-dt/tau); h_next=min(h_free,book_height)',
        state_initialization='Resting height at the beginning of every selected interval',
        marker_mapping='y_i=table_y+(y_i_reference-table_y)*h/H; x_i=x_i_reference',
        assumptions=['uniform vertical strain','horizontal prescribed plate','negligible inertia',
                     'fixed length and width','no identified contact force or separate stiffness/damping'],
        timing_assumption=f"Every exported frame corresponds to one uniformly spaced {config['capture_fps']}-fps capture sample.",
        provenance='Video foam observations supervise fitting; only book motion drives subsequent simulation.')
    (processed/'parameters.json').write_text(json.dumps(parameters,indent=2))
    (processed/'metrics.json').write_text(json.dumps(results,indent=2))
    with (processed/'simulation_inputs.csv').open('w',newline='') as handle:
        writer=csv.writer(handle);writer.writerow(['trial','frame','book_height_mm','estimated_input'])
        for trial in trials:
            writer.writerows(zip(np.full(len(trial['frames']),trial['id']),trial['frames'],
                                 trial['book_height_mm'],trial['book_input_estimated']))
    make_plot(trials,config,tau,visuals)
    print(json.dumps(dict(parameters=parameters,metrics=results),indent=2))
    print('Review plots and tracking before accepting the fitted material response.')


def make_plot(trials,config,tau,visuals):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    visuals.mkdir(parents=True,exist_ok=True)
    columns=2;rows=int(np.ceil(len(trials)/columns))
    fig,axes=plt.subplots(rows,columns,figsize=(12,3.7*rows),squeeze=False)
    for ax,trial in zip(axes.flat,trials):
        t=(trial['frames']-trial['frames'][0])/config['capture_fps']
        h,contact,_=predict(trial,config,tau)
        ax.plot(t,trial['measured_height_mm'],'.',ms=3,label='Marker-derived height')
        ax.plot(t,h,label='Predicted foam height')
        ax.plot(t,np.minimum(trial['book_height_mm'],config['dimensions_mm'][2]*1.2),'--',alpha=.5,label='Prescribed book ceiling (capped)')
        ax.set(title=f"Press {trial['id']} / {trial['role']}",xlabel='Capture time from interval start (s)',ylabel='Height (mm)')
        ax.grid(alpha=.2)
    for ax in axes.flat[len(trials):]:ax.set_visible(False)
    axes.flat[0].legend(fontsize=8);fig.tight_layout();fig.savefig(visuals/'fit_results.png',dpi=160);plt.close(fig)


def draw_book_input(display,book,angle,table,pixels_per_mm,x_range,sx,sy,estimated=False):
    """Draw measured orientation, or a height-only marker when angle is unknown."""
    if not np.isfinite(book):
        return False
    center_y=table-book*pixels_per_mm
    left,right=x_range
    center=(left+right)/2
    color=(40,190,255) if estimated else (255,190,70)
    angle_unknown=not np.isfinite(angle) or abs(angle)>=85
    if angle_unknown:
        point=(int(center*sx),int(center_y*sy))
        cv2.drawMarker(display,point,color,cv2.MARKER_DIAMOND,12,2)
        cv2.putText(display,'BOOK HEIGHT ONLY',(point[0]+10,max(15,point[1]-8)),
                    cv2.FONT_HERSHEY_SIMPLEX,.4,color,1)
    else:
        slope=np.tan(np.radians(angle))
        y0=center_y+slope*(left-center)
        y1=center_y+slope*(right-center)
        cv2.line(display,(int(left*sx),int(y0*sy)),(int(right*sx),int(y1*sy)),color,2)
    return angle_unknown


def preview(config_path,trial_id,tracking_only=False,model_path=None):
    config,video,processed,visuals,observations=load_observations(config_path)
    if not 1<=trial_id<=len(config['trials']):raise ValueError('Select an existing trial.')
    annotation=config['trials'][trial_id-1]
    mask=observations['trial_ids']==trial_id
    data={key:value[mask] for key,value in observations.items()}
    reference=data['reference_xy'][0]
    predicted=None
    if not tracking_only:
        parameters=json.loads((model_path or processed/'parameters.json').read_text())
        if model_path is None and (parameters['config_hash']!=digest(config_path)
            or parameters['observations_hash']!=digest(processed/'observations.npz')):
            raise ValueError('Fit is stale. Refit before rendering.')
        trial=prepare_trials(config,observations,parameters.get('max_book_gap',0))[trial_id-1]
        data['book_height_mm']=trial['book_height_mm']
        data['book_input_estimated']=trial['book_input_estimated']
        heights,contact,predicted=predict(trial,config,parameters['recovery_time_s'])
    visuals.mkdir(parents=True,exist_ok=True)
    destination=visuals/f'{"tracking" if tracking_only else "simulation"}_press_{trial_id}.mp4'
    capture=cv2.VideoCapture(str(video));capture.set(cv2.CAP_PROP_POS_FRAMES,annotation['start'])
    temporary=destination.with_name(destination.stem+'.partial.mp4')
    writer=cv2.VideoWriter(str(temporary),cv2.VideoWriter_fourcc(*'mp4v'),30,(1600,900))
    try:
        if not writer.isOpened():raise ValueError('Cannot create preview video.')
        table=float(data['calibrated_table_y_px'][0]);pixels_per_mm=float(data['calibrated_px_per_mm'][0])
        for index,frame_index in enumerate(data['frames']):
            ok,frame=capture.read()
            if not ok:raise ValueError(f'Cannot decode frame {frame_index}')
            image=np.full((900,1600,3),25,dtype=np.uint8)
            display=cv2.resize(frame,(960,540))
            sx=960/frame.shape[1];sy=540/frame.shape[0]
            for marker_id,point in enumerate(data['markers'][index]):
                if np.isfinite(point).all():
                    x,y=np.round(point*[sx,sy]).astype(int)
                    cv2.circle(display,(x,y),4,(70,240,110),1)
                    cv2.putText(display,str(marker_id+1),(x+5,y-4),cv2.FONT_HERSHEY_SIMPLEX,.35,(70,240,110),1)
            book=data['book_height_mm'][index]
            estimated_input=bool(data.get('book_input_estimated',np.zeros(len(data['frames']),bool))[index])
            angle_unknown=draw_book_input(display,book,data['book_angle_deg'][index],table,
                                          pixels_per_mm,config['book_x_range'],sx,sy,estimated_input)
            if predicted is not None:
                for point in predicted[index]:
                    if not np.isfinite(point).all():continue
                    x,y=np.round(point*[sx,sy]).astype(int)
                    cv2.drawMarker(display,(x,y),(40,170,255),cv2.MARKER_CROSS,9,1)
            image[80:620,:960]=display
            title='TRACKING REVIEW' if tracking_only else 'BOOK-DRIVEN SIMULATION'
            cv2.putText(image,title,(25,35),cv2.FONT_HERSHEY_SIMPLEX,.85,(240,240,240),2)
            phase='' if tracking_only else ('CONTACT' if contact[index] else 'FREE RECOVERY')
            if not tracking_only and trial['book_input_estimated'][index]:
                phase+=' / ESTIMATED BOOK INPUT'
            if angle_unknown:
                phase+=' / BOOK ANGLE UNKNOWN'
            lines=[f"Press {trial_id} ({annotation['role']}); frame {frame_index}; {phase}",
                   f"Book input {book:.2f} mm; marker-derived height {data['measured_height_mm'][index]:.2f} mm",
                   'Green circles: observed dots. Book line: measured angle; diamond: height only.',
                   'Orange crosses: model predictions. No observed foam height drives the simulation.',
                   'Uniform vertical strain; stationary table; maroon-book detector is capture-specific.',
                   f"Playback {config['capture_fps']/30:.1f}x slow motion; reported capture rate {config['capture_fps']} fps."]
            for j,line in enumerate(lines):
                cv2.putText(image,line,(25,665+j*31),cv2.FONT_HERSHEY_SIMPLEX,.65,(230,230,230),1,cv2.LINE_AA)
            if not tracking_only:
                height=float(heights[index]);length,width,_=config['dimensions_mm']
                vertices=np.array([[x,y,z] for z in (0,height) for y in (0,width) for x in (0,length)])
                projected=np.round(vertices@np.array([[2.4,-1.,0],[.2,.5,-4.]]).T+[1100,450]).astype(np.int32)
                for ids,color in [([2,3,7,6],(80,180,220)),([1,3,7,5],(55,145,185)),([4,5,7,6],(130,210,240))]:
                    cv2.fillConvexPoly(image,projected[ids],color)
                    cv2.polylines(image,[projected[ids]],True,(230,240,245),1)
            else:
                count=np.isfinite(data['markers'][index]).all(axis=1).sum()
                cv2.putText(image,f'{count}/{len(reference)} dots observed',(1010,260),cv2.FONT_HERSHEY_SIMPLEX,.8,(100,230,140),2)
            writer.write(image)
    finally:
        capture.release()
        writer.release()
    temporary.replace(destination)
    print('Saved',destination)



def evaluate(config_path,model_path,max_book_gap=0):
    config,video,processed,visuals,observations=load_observations(config_path)
    parameters=json.loads(model_path.read_text())
    if not np.allclose(parameters['dimensions_mm'],config['dimensions_mm']):
        raise ValueError('Object dimensions differ from fitted model.')
    if config['video']==json.loads((model_path.parent/'tracking_metadata.json').read_text())['config']['video']:
        raise ValueError('Final evaluation requires a different video from training.')
    trials=prepare_trials(config,observations,max_book_gap)
    results=evaluate_trials(trials,config,parameters['recovery_time_s'])
    (processed/'test_metrics.json').write_text(json.dumps(dict(model_path=str(model_path.resolve()),
        model_hash=digest(model_path),metrics=results),indent=2))
    make_plot(trials,config,parameters['recovery_time_s'],visuals)
    print(json.dumps(results,indent=2))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='command',required=True)
    setup=sub.add_parser('setup')
    setup.add_argument('--video',type=Path,default=DEFAULT_VIDEO)
    setup.add_argument('--config',type=Path)
    setup.add_argument('--fps',type=float,default=120)
    for name in ['track','fit','preview','evaluate']:
        command=sub.add_parser(name)
        command.add_argument('--config',type=Path,default=DEFAULT_CONFIG)
        if name=='preview':
            command.add_argument('--trial',type=int,default=1)
            command.add_argument('--tracking-only',action='store_true')
            command.add_argument('--model',type=Path)
        if name in ['fit','evaluate']:
            command.add_argument('--max-book-gap',type=int,default=0,
                                 help='Explicitly permit estimating book-input gaps up to this many frames.')
        if name=='evaluate':command.add_argument('--model',type=Path,required=True)
    args=parser.parse_args()
    if args.command=='setup':
        from displacement_setup import open_setup
        config=args.config or PROJECT/'data'/'annotations'/f'{args.video.stem}.json'
        open_setup(args.video,config,args.fps)
    elif args.command=='track':track(args.config)
    elif args.command=='fit':fit(args.config,args.max_book_gap)
    elif args.command=='preview':preview(args.config,args.trial,args.tracking_only,args.model)
    else:evaluate(args.config,args.model,args.max_book_gap)


if __name__=='__main__':
    main()
