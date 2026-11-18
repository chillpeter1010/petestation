"""Conservative appearance-locked candidate selection, not player recognition."""
import cv2
import numpy as np

TRACKER_VERSION='appearance-lock-v3'

def shirt_histogram(bgr,points):
    hull=cv2.convexHull(np.round(points[[11,12,24,23]]).astype('int32'))
    mask=np.zeros(bgr.shape[:2],dtype='uint8');cv2.fillConvexPoly(mask,hull,255)
    mask=cv2.erode(mask,np.ones((3,3),dtype='uint8'))
    if cv2.countNonZero(mask)<20:return None
    hist=cv2.calcHist([cv2.cvtColor(bgr,cv2.COLOR_BGR2HSV)],[0,1,2],mask,[12,4,4],[0,180,0,256,0,256])
    return cv2.normalize(hist,None,alpha=1,norm_type=cv2.NORM_L1)

class AppearanceLock:
    def __init__(self,width,height):
        self.size=np.array([width,height]);self.previous=None;self.anchor=None
        self.torso=None;self.last_time=None

    def choose(self,candidates,now):
        scored=[]
        for index,c in enumerate(candidates):
            p=c['image'];hip=p[[23,24]].mean(axis=0)/self.size
            torso=np.linalg.norm((p[[11,12]].mean(axis=0)-p[[23,24]].mean(axis=0))/self.size)
            conf=min(c['confidence'][23],c['confidence'][24]);hist=c['histogram']
            if conf<.6 or hist is None:continue
            if self.anchor is None:
                # Foreground mound seed; must still be checked by the user.
                ankle=np.max(p[[27,28],1])/self.size[1]
                if not(.25<hip[0]<.62 and hip[1]>.42 and ankle>.65):continue
                cost=np.linalg.norm(hip-[.43,.60])+.25*(1-ankle)
                distance=0
            else:
                distance=float(cv2.compareHist(self.anchor,hist,cv2.HISTCMP_BHATTACHARYYA))
                elapsed=now-self.last_time
                movement=np.linalg.norm(hip-self.previous)
                # Never switch to the nearest person just because the pitcher disappeared.
                if distance>.48 or movement>min(.14,.025+elapsed*.22):continue
                if not .5<torso/self.torso<1.8:continue
                cost=distance+movement*3+abs(np.log(torso/self.torso))*.08
            scored.append((cost,index,hip,torso,distance))
        if not scored:return None
        scored.sort(key=lambda x:x[0])
        if self.anchor is not None and len(scored)>1 and scored[1][0]-scored[0][0]<.06:
            return None # ambiguous candidates remain missing
        _,index,hip,torso,distance=scored[0]
        if self.anchor is None:
            self.anchor=candidates[index]['histogram'].copy();self.torso=torso
        self.previous=hip;self.last_time=now
        return index,dict(appearanceDistance=distance,seedAcceptedByUser=False)


class MoundTrack(AppearanceLock):
    """Foreground temporal candidate inside a declared pitcher-only crop.

    The fixed shirt template cannot hard-gate a rotating white uniform. Position,
    size and ambiguity gates remain; colour is a score, not identity proof.
    """
    def choose(self,candidates,now):
        if self.anchor is None:return super().choose(candidates,now)
        scored=[]
        for i,c in enumerate(candidates):
            p=c['image'];hip=p[[23,24]].mean(axis=0)/self.size
            torso=np.linalg.norm((p[[11,12]].mean(axis=0)-p[[23,24]].mean(axis=0))/self.size)
            hist=c['histogram']
            if hist is None or min(c['confidence'][23],c['confidence'][24])<.6:continue
            if not(.18<hip[0]<.57 and .42<hip[1]<.86):continue
            movement=np.linalg.norm(hip-self.previous);elapsed=now-self.last_time
            if movement>min(.10,.018+elapsed*.15) or not .5<torso/self.torso<1.8:continue
            distance=float(cv2.compareHist(self.anchor,hist,cv2.HISTCMP_BHATTACHARYYA))
            if distance>.85:continue
            scored.append((movement*5+abs(np.log(torso/self.torso))*.1+distance*.05,i,hip,distance))
        scored.sort(key=lambda x:x[0])
        if not scored or (len(scored)>1 and scored[1][0]-scored[0][0]<.035):return None
        _,i,hip,distance=scored[0];self.previous=hip;self.last_time=now
        return i,dict(appearanceDistance=distance,seedAcceptedByUser=False,mode='mound-crop-temporal-v1')
