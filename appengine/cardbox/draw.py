""" Chart and graph generating library """

### IMPORTS ###
import random
import xml.dom.minidom as minidom

### FUNCTIONS ###

def create_dom_element(doc, node, attrs={}):
    elem = doc.createElement(node)
    for (k,v) in attrs.items():
        elem.setAttribute(k,v)
    return elem

def svg_empty(width=100,height=100):
    dom = minidom.getDOMImplementation('')
    doctype = dom.createDocumentType('svg', '-//W3C//DTD SVG 1.1//EN', 'http://www.w3.org/Graphics/SVG/1.1/DTD/svg11.dtd')
    svg = dom.createDocument('http://www.w3.org/2000/svg','svg',doctype)
    root = svg.documentElement
    root.setAttribute('version','1.1')
    root.setAttribute('xmlns',"http://www.w3.org/2000/svg")
    root.setAttribute('x','0')
    root.setAttribute('y','0')
    root.setAttribute('width',str(width))
    root.setAttribute('height',str(height))
    return svg

def svg_cardstack(height, top_text):
    svg      = svg_empty(80,100)
    root     = svg.documentElement
    defs     = create_dom_element(svg,'defs')
    gradient = create_dom_element(svg,'radialGradient',{'id':'GRAD','cx':'0','cy':'0','r':'100%'})
    stop1    = create_dom_element(svg,'stop',{'offset':'0','style':"stop-color:#FFFFFF"})
    stop2    = create_dom_element(svg,'stop',{'offset':'100%','style':"stop-color:#E6E6B8"})
    gradient.appendChild(stop1)
    gradient.appendChild(stop2)
    root.appendChild(defs)
    defs.appendChild(gradient)
    
    for i in range(height):
        r = -(random.random()*40+10)
        y = 70 - i*3
        g = svg.createElement('g')
        g.setAttribute('transform','translate(37,%d)'%y)
        rect = svg.createElement('rect')
        attrs = {
            'x':'-30',
            'y':'-12',
            'width':'60',
            'height':'35',
            'transform':'scale(1,0.5) rotate(%d) '%r,
            'fill': "url(#GRAD)",
            'stroke':'#000000',
            'stroke-width':'2'
        }
        for (k,v) in attrs.items():
            rect.setAttribute(k,v)
        root.appendChild(g)
        g.appendChild(rect)
        if i == height-1:
            text = svg.createElement('text')
            attrs['x'] = '-25'
            attrs['y'] = '10'
            attrs['stroke-width'] = '1'
            for (k,v) in attrs.items():
                text.setAttribute(k,v)
            text.appendChild(svg.createTextNode(top_text[:4]))
            g.appendChild(text)
    return root.toprettyxml()
    
def rescale_datetimes(dates, old_range_min=None, old_range_max=None, new_range_min=0, new_range_max=1):
    ascending = sorted(dates)
    if old_range_min is None: 
        old_range_min = ascending[0]
    if old_range_max is None:
        old_range_max = ascending[-1]
    omn = time.mktime(old_range_min.timetuple())
    omx = time.mktime(old_range_max.timetuple())
    nmn,nmx = new_range_min, new_range_max
    timestamps = map(lambda x: time.mktime(x.timetuple()), dates)
    scaled =  map(lambda x: ((x-omn)/float(omx-omn)) * (nmx-nmn) + nmn, timestamps)
    return scaled

### CLASSES ###

class TimelineChart(object):
    
    max_date_labels = 7
    
    def __init__(self, **kwds):
        self.gcparams = {}
        self.lines = []
        self.line_fills = []
        self.ranges = []
        self.size = kwds.get('size','470x200')
        self.times = set([])
    
    def add_line(self, times, data, label='', color='94c15d',thickness=3):
        if len(times) > 1:
            self.times = self.times.union(times)
            self.lines.append({'times':times,
                               'data':data,
                               'label':label,
                               'color':color,
                               'thickness':thickness})
    
    def add_line_fill(self, color, start_line, end_line):
        self.line_fills.append({'color':color,'start_line':start_line,'end_line':end_line})
        
    def add_range_markers(self, range_starts, range_ends):
        self.ranges.append({'starts':range_starts,'ends':range_ends})
        
    def rescale_all(self, rng=100):
        if len(self.times) > 1:
            times = sorted(self.times)
            first,last = times[0],times[-1]
            scaledtimes = rescale_datetimes(times, first, last, new_range_max=rng)
            for l in self.lines:
                l['scaled'] = rescale_datetimes(l['times'],first, last, new_range_max=rng)
            for r in self.ranges:
                r['scaled'] = zip(rescale_datetimes(r['starts'],first, last, new_range_max=1),
                                rescale_datetimes(r['ends'],first, last, new_range_max=1))
            self.labels = []
            self.labels.append((first, scaledtimes[0]))
            min_distance = (last-first)/self.max_date_labels
            for (t,s) in zip(times, scaledtimes):
                if t > self.labels[-1][0] + min_distance:
                    self.labels.append((t,s))

    def render(self):
        if len(self.times) < 2:
            self.empty_chart()
            return
        self.rescale_all()
        lines = [','.join(['%.1f'%t for t in l['scaled']]) + '|' + 
                 ','.join(['%.1f'%d for d in l['data']]) 
                    for l in self.lines]
        lines = '|'.join(lines)
        ranges = [['R,94c15d44,0,%s,%s'%(a,b) for (a,b) in r['scaled']] 
                    for r in self.ranges]
        ranges = '|'.join(ranges)
        linefills = '|'.join(['b,%s,%d,%d,0'%(lf['color'],
                                              lf['start_line'],
                                              lf['end_line']) for lf in self.line_fills])
        legend = '|'.join([l['label'] for l in self.lines])
        colors = ','.join([l['color'] for l in self.lines])
        linestyle = '|'.join([str(l['thickness']) for l in self.lines])
        labels = '|'.join([l[0].strftime("%b %d %%27%y") for l in self.labels])
        label_positions = ','.join(['%.1f'%l[1] for l in self.labels])
        max_val = max(0.1,max([max(l['data']) for l in self.lines]))
        ideal_spacing = (100/float(max_val)) * max(max_val//5.0,1)
        # Set parameters
        self.gcparams['cht']  = 'lxy'
        self.gcparams['chxt'] = 'x,y'
        self.gcparams['chds'] = ','.join([('0,100,0,%.0f'%(max_val)) for i in range(len(self.lines))])
        self.gcparams['chg']  = '0,%.1f'%ideal_spacing
        self.gcparams['chf']  = 'bg,s,65432100'
        # Dynamic parameters
        self.gcparams['chd']  = 't:'+lines
        self.gcparams['chco'] = colors
        self.gcparams['chls'] = linestyle
        self.gcparams['chm']  = ranges + ('|' if ranges and linefills else '') + linefills
        self.gcparams['chdl'] = legend
        self.gcparams['chxr'] = '1,0,%.2f'%max_val
        self.gcparams['chxl'] = '0:|'+labels
        self.gcparams['chxp'] = '0,'+label_positions
        
    def empty_chart(self):
        self.gcparams['chst'] = 'd_text_outline'
        self.gcparams['chld'] = '8A1F11|16|h|FFFFFF|b|Generating+data.+Come+back+in+a+minute.'

    def url(self):
        self.render()
        return ("http://chart.apis.google.com/chart?chs=%s&%s"%(self.size,
            '&'.join(['%s=%s'%(k,v) for (k,v) in self.gcparams.items()])))
            
    def img(self):
        return mark_safe("<img src='%s'/>"%self.url())

    
if __name__ == "__main__":
    print svg_cardstack(10,"cbx")
