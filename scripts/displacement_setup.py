"""Interactive setup for marker observations and prescribed book motion."""
import json
from pathlib import Path
import tkinter as tk
from tkinter import ttk,messagebox
import cv2
import numpy as np
from PIL import Image,ImageTk
from displacement_tracking import detect_book,snap_markers


class Setup:
    def __init__(self,window,video,output,fps):
        self.window=window;self.video=video.resolve();self.output=output
        self.capture=cv2.VideoCapture(str(self.video))
        if not self.capture.isOpened():
            raise ValueError(f'Cannot open {video}')
        self.count=int(self.capture.get(cv2.CAP_PROP_FRAME_COUNT))
        self.frame_index=0;self.mode=None;self.photo=None;self.book_clicks=[]
        self.document=dict(version=1,video=str(self.video),capture_fps=fps,
                           frame_count=self.count,dimensions_mm=[190,75,35],
                           reference_frame=0,markers=[],trials=[])
        if output.exists():
            self.document=json.loads(output.read_text())
            if Path(self.document['video']).resolve()!=self.video:
                raise ValueError('This configuration belongs to another video.')
        self.status=tk.StringVar(value='First set geometry and markers on a resting frame.')
        self.summary=tk.StringVar()
        width=min(1250,window.winfo_screenwidth()-80)
        height=min(850,window.winfo_screenheight()-100)
        window.geometry(f'{width}x{height}+20+20')
        window.title('Book input and foam markers')
        window.columnconfigure(0,weight=1);window.rowconfigure(1,weight=1)
        ttk.Label(window,text='1 Resting reference  |  2 Select dots  |  3 Book underside  |  4 Trial intervals',padding=5).grid(row=0,column=0)
        self.canvas=tk.Canvas(window,width=700,height=180,bg='#17191d',highlightthickness=0)
        self.canvas.grid(row=1,column=0,sticky='nsew')
        self.canvas.bind('<Configure>',lambda event:self.draw())
        self.canvas.bind('<Button-1>',self.click)
        self.slider=tk.Scale(window,from_=0,to=self.count-1,orient='horizontal',showvalue=False,
                             command=lambda value:self.seek(int(float(value))))
        self.slider.grid(row=2,column=0,sticky='ew')
        navigation=ttk.Frame(window);navigation.grid(row=3,column=0)
        for label,delta in [('-10',-10),('Previous',-1),('Next',1),('+10',10)]:
            ttk.Button(navigation,text=label,command=lambda d=delta:self.seek(self.frame_index+d)).pack(side='left',padx=3)
        self.frame_entry=tk.StringVar(value='0')
        ttk.Entry(navigation,textvariable=self.frame_entry,width=7).pack(side='left',padx=5)
        ttk.Button(navigation,text='Go',command=self.goto).pack(side='left')
        reference=ttk.Frame(window);reference.grid(row=4,column=0,pady=4)
        ttk.Button(reference,text='Set resting reference here',command=self.set_reference).pack(side='left',padx=3)
        ttk.Button(reference,text='Mark foam TOP then TABLE',command=lambda:self.set_mode('top')).pack(side='left',padx=3)
        ttk.Button(reference,text='Select ink dots',command=self.marker_mode).pack(side='left',padx=3)
        ttk.Button(reference,text='Clear dots',command=self.clear_markers).pack(side='left',padx=3)
        ttk.Button(window,text='At a frame with book visible: mark TWO underside points',
                   command=self.book_mode).grid(row=5,column=0,pady=3)
        trials=ttk.Frame(window);trials.grid(row=6,column=0,pady=4)
        self.start=tk.StringVar(value='0');self.stop=tk.StringVar(value='0');self.role=tk.StringVar(value='train')
        ttk.Button(trials,text='Start here (foam at rest)',command=lambda:self.start.set(str(self.frame_index))).pack(side='left')
        ttk.Entry(trials,textvariable=self.start,width=7).pack(side='left',padx=3)
        ttk.Button(trials,text='End here (settled)',command=lambda:self.stop.set(str(self.frame_index))).pack(side='left')
        ttk.Entry(trials,textvariable=self.stop,width=7).pack(side='left',padx=3)
        ttk.Combobox(trials,textvariable=self.role,values=['train','validation','test'],state='readonly',width=11).pack(side='left')
        ttk.Button(trials,text='Add press',command=self.add_trial).pack(side='left',padx=3)
        ttk.Button(trials,text='Undo last press',command=self.undo_trial).pack(side='left',padx=3)
        ttk.Label(window,textvariable=self.summary,padding=3).grid(row=7,column=0)
        ttk.Label(window,textvariable=self.status,padding=4,wraplength=1000).grid(row=8,column=0)
        ttk.Button(window,text='Save configuration',command=self.save).grid(row=9,column=0,pady=5)
        window.bind('<Left>',lambda event:self.step_key(event,-1))
        window.bind('<Right>',lambda event:self.step_key(event,1))
        window.protocol('WM_DELETE_WINDOW',self.close)
        self.seek(self.document['reference_frame'])

    def step_key(self,event,delta):
        if not isinstance(event.widget,(tk.Entry,ttk.Entry,ttk.Combobox)):
            self.seek(self.frame_index+delta*(10 if event.state&1 else 1))
            return 'break'

    def goto(self):
        try:self.seek(int(self.frame_entry.get()))
        except ValueError:messagebox.showerror('Frame','Enter an integer.')

    def seek(self,index):
        index=max(0,min(self.count-1,int(index)))
        if hasattr(self,'frame') and index==self.frame_index:
            return
        self.capture.set(cv2.CAP_PROP_POS_FRAMES,index)
        ok,frame=self.capture.read()
        if not ok:
            self.status.set(f'Cannot decode frame {index}');return
        self.frame_index=index;self.frame=frame
        self.slider.set(index);self.frame_entry.set(str(index));self.draw()

    def draw(self):
        if not hasattr(self,'frame'):return
        picture=Image.fromarray(cv2.cvtColor(self.frame,cv2.COLOR_BGR2RGB))
        width=max(200,self.canvas.winfo_width());height=max(120,self.canvas.winfo_height())
        picture.thumbnail((width,height))
        self.mapping=(width/2-picture.width/2,height/2-picture.height/2,
                      picture.width/self.frame.shape[1],picture.height/self.frame.shape[0])
        self.photo=ImageTk.PhotoImage(picture);self.canvas.delete('all')
        self.canvas.create_image(width/2,height/2,image=self.photo)
        left,upper,sx,sy=self.mapping
        if self.frame_index==self.document['reference_frame']:
            for index,(x,y) in enumerate(self.document['markers']):
                x=left+x*sx;y=upper+y*sy
                self.canvas.create_oval(x-4,y-4,x+4,y+4,outline='#3bff86',width=2)
                self.canvas.create_text(x+10,y,text=str(index+1),fill='#3bff86')
            for key,color in [('rest_top_y_px','#3bff86'),('table_y_px','#65baff')]:
                if key in self.document:
                    y=upper+self.document[key]*sy
                    self.canvas.create_line(left,y,left+picture.width,y,fill=color)
        if self.frame_index==self.document.get('book_reference_frame'):
            points=self.document.get('book_points',self.book_clicks)
            if len(points)==2:
                x0,y0=points[0];x1,y1=points[1]
                self.canvas.create_line(left+x0*sx,upper+y0*sy,left+x1*sx,upper+y1*sy,fill='#ffcc65',width=2)
        ranges=' | '.join(f"{i+1}: {t['start']}-{t['stop']} ({t['role']})" for i,t in enumerate(self.document['trials']))
        self.summary.set(f"Frame {self.frame_index}/{self.count-1}; {len(self.document['markers'])} dots.  "+ranges)

    def set_reference(self):
        if self.document['markers'] or 'rest_top_y_px' in self.document:
            if not messagebox.askyesno('Reset reference','Changing reference clears dots and geometry calibration. Continue?'):return
        self.document.update(reference_frame=self.frame_index,markers=[])
        self.document.pop('rest_top_y_px',None);self.document.pop('table_y_px',None);self.draw()

    def set_mode(self,mode):
        self.seek(self.document['reference_frame']);self.mode=mode
        self.status.set('Click the foam upper silhouette, then where its bottom meets the table, at the same central x position.')

    def marker_mode(self):
        self.seek(self.document['reference_frame']);self.mode='markers'
        self.status.set('Click 6-12 distinct ink dots across at least two vertical rows. Click Select ink dots again if you navigate away.')

    def clear_markers(self):
        self.document['markers']=[];self.draw()

    def book_mode(self):
        self.book_clicks=[];self.mode='book'
        self.document['book_reference_frame']=self.frame_index
        self.document.pop('book_points',None)
        self.status.set('Click two points along the BOOK UNDERSIDE, spanning the central foam face. Use a sharp frame with the book visible.')

    def click(self,event):
        if self.mode is None:return
        left,upper,sx,sy=self.mapping
        x=(event.x-left)/sx;y=(event.y-upper)/sy
        if not 0<=x<self.frame.shape[1] or not 0<=y<self.frame.shape[0]:return
        if self.mode=='markers':
            self.document['markers'].append([round(x,2),round(y,2)])
        elif self.mode=='top':
            self.document['rest_top_y_px']=round(y,2);self.mode='table'
            self.status.set('Now click the foam bottom where it meets the table.')
        elif self.mode=='table':
            self.document['table_y_px']=round(y,2);self.mode=None
        elif self.mode=='book':
            self.book_clicks.append([round(x,2),round(y,2)])
            if len(self.book_clicks)==2:
                self.document['book_points']=self.book_clicks.copy();self.mode=None
        self.draw()

    def add_trial(self):
        try:
            first,last=int(self.start.get()),int(self.stop.get())
            if not 0<=first<last<self.count:raise ValueError('Require start < end within the video.')
            for trial in self.document['trials']:
                if first<=trial['stop'] and last>=trial['start']:
                    raise ValueError('Press intervals must not overlap.')
            self.document['trials'].append(dict(start=first,stop=last,role=self.role.get()))
            self.document['trials'].sort(key=lambda trial:trial['start']);self.draw()
        except ValueError as error:messagebox.showerror('Press interval',str(error))

    def undo_trial(self):
        if self.document['trials']:self.document['trials'].pop();self.draw()

    def save(self):
        try:
            document=self.document
            if len(document['markers'])<6:raise ValueError('Select at least six dots.')
            if not document.get('rest_top_y_px',1e9)<document.get('table_y_px',-1):
                raise ValueError('Set resting TOP and TABLE first.')
            if len(document.get('book_points',[]))!=2:raise ValueError('Set two book underside points.')
            if not document['trials']:raise ValueError('Add complete press intervals.')
            points=np.asarray(document['markers'])
            if np.ptp(points[:,1])<80:raise ValueError('Choose dots across multiple vertical rows.')
            roi=[max(0,points[:,0].min()-60),max(0,document['rest_top_y_px']-40),
                 min(self.frame.shape[1],points[:,0].max()+60),min(self.frame.shape[0],document['table_y_px']+10)]
            self.capture.set(cv2.CAP_PROP_POS_FRAMES,document['reference_frame'])
            ok,reference=self.capture.read()
            if not ok:raise ValueError('Cannot read resting reference.')
            document['markers']=snap_markers(reference,points,roi).tolist()
            document['marker_roi']=list(map(int,roi))
            self.capture.set(cv2.CAP_PROP_POS_FRAMES,document['book_reference_frame'])
            ok,book=self.capture.read()
            if not ok:raise ValueError('Cannot read book reference.')
            endpoints=np.asarray(document['book_points'])
            x_range=sorted(endpoints[:,0].tolist())
            if x_range[1]-x_range[0]<200:raise ValueError('Book underside points should span at least 200 pixels.')
            raw_y,tilt,coverage=detect_book(book,x_range,document['table_y_px'])
            if not np.isfinite(raw_y):raise ValueError('Maroon book segmentation failed at reference. Choose a clearer book frame.')
            document['book_x_range']=x_range
            document['book_binding_offset_px']=float(np.mean(endpoints[:,1])-raw_y)
            document['video_size_bytes']=self.video.stat().st_size
            document['video_modified_ns']=self.video.stat().st_mtime_ns
            self.output.parent.mkdir(parents=True,exist_ok=True)
            temporary=self.output.with_suffix('.tmp');temporary.write_text(json.dumps(document,indent=2));temporary.replace(self.output)
            self.status.set(f'Saved {self.output}.');self.draw()
        except (ValueError,OSError) as error:messagebox.showerror('Setup incomplete',str(error))

    def close(self):
        self.capture.release();self.window.destroy()


def open_setup(video,output,fps):
    root=tk.Tk()
    try:Setup(root,video,output,fps)
    except Exception:
        root.destroy();raise
    root.mainloop()
