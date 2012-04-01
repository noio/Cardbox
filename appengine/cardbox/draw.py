""" Chart and graph generating library """

### IMPORTS ###
import random
import xml.dom.minidom as minidom

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
    
if __name__ == "__main__":
    print svg_cardstack(10,"cbx")
