/** CLASSES **/

/**
 * Ribbon is an expanding navigation menu, using hierarchical 
 * horizontal bars.
 */
var Ribbon = new Class({
    Implements: [Options],
    
    initialize: function(id, options){
        this.navbar = $(id);
        
    }
})

/**
 * BrowseTable implements functions for displaying a table
 * for lists of items on the server
 */
var BrowseTable = new Class({
    Implements: [Options,Events],
    options:{
        kind: null,
        actions: ['select'],
        allowedFilters: {'factsheet':['subject']},
        filters: {},
        showControl: true
    },

    initialize: function(id, options){
        this.setOptions(options);
        this.element = $(id);
        this.element.addClass('browser');
        this.element.set('spinner',{message:'Wait a moment...'});
        this.control = new Element('form',{'class':'inline'}).inject(new Element('div').inject(this.element));
        this.element.grab(new Element('div',{'class':'squish'}).grab(new Element('table')));
        this.table = new HtmlTable(this.element.getElement('table'),{
            'selectable':true,
            'sortable':true,
            'sortReverse':true,
            'allowMultiSelect':false
        });
       
    },
    
    update: function(opts){
        this.setOptions(opts);
        this.redraw();
        this.refresh();
    },
    
    refresh: function(){
        this.table.element.spin();
        var dataRequest = new Request.JSON({
            url: "/browse_data/"+this.options.kind.toLowerCase(), 
            onSuccess: function(data){
                this.addData(data);
            }.bind(this)
        }).get(this.options.filters);
    },
    
    redraw: function(){
        // Draw control bar
        this.control.empty();
        if (!this.options.showControl) {return;}
        var h = this.options.allowedFilters[this.options.kind];
        if($chk(h)){
             h.each(function(value, index){
                var label = new Element('label',{'html':value+': '});
                var field = new Element('input',{'type':'text'});
                this.control.adopt(label, field);
                var o = new Observer(field, function(e){
                    this.addFilter(value, e);
                }.bind(this), {'delay':1000});
            }.bind(this));
        }
    },
    
    addFilter: function(field, value){
        this.options.filters[field] = value;
        this.refresh();
    },
    
    addData: function(data){
        // Redraw table
        this.table.element.unspin();
        this.data = data;
        this.table.empty();
        var headers = this.data.headers.slice(2);
        headers.unshift('view');
        headers = this.options.actions.concat(headers);
        this.table.setHeaders(headers);
        this.data.rows.each(function(row,idx){
            this.addRow(row);
        },this);
        headers.each(function(header,idx){
            var col = new Element('col',{'class':'column-'+header})
            col.inject(this.element.getElement('thead'),'before');
        }.bind(this))
    },
    
    getNamedRowData: function(id){
        var rd = this.getRowData(id);
        return rd.associate(this.data.headers);
    },
    
    getRowData: function(id){
        return this.element.getElement('tr[id='+id+']').retrieve('rowData');
    },
    
    addRow: function(rowData){
        if (this.getRowIds().contains(rowData[0])) {return;}
        var tr = rowData.slice(2);
        var viewLink = new Element('a',{'href':rowData[1],
                                        'target':'_blank',
                                        'html':'view'});
        tr.unshift(viewLink);
        this.options.actions.each(function(a,idx){
            var action = new Element('a',{'href':'#',
                                          'html':a,
                                          'class':'action_'+a});
            action.addEvent('click',function(element){
                this.fireEvent('action_'+a,[rowData[0]]);
            }.bind(this));
            tr.unshift(action);
        },this);
        var rowElement = this.table.push(tr).tr;
        rowElement.set('id',rowData[0]);
        rowElement.store('rowData',rowData);
    },
    
    removeRow: function(id){
        return this.element.getElement('tr[id='+id+']').dispose();
    },
    
    getRowIds: function(){
        return this.element.getElements('tbody tr').map(function(el){
            return el.retrieve('rowData')[0];
        });
    }
});


/**
 * A mappingselector allows the user to select which
 * values of the factsheet go in which fields on the template
 */
var MappingSelector = new Class({
    
    initialize: function(id, field){
        this.element = $(id);
        this.element.addClass('mapper');
        this.outputField = $(field);
        this.mapping = JSON.decode(this.outputField.get('value'));
        if (this.mapping === null) {this.mapping = {};}
    },
    
    setValues: function(values){
        this.values = ['None'].combine(values);
        this.redraw();
    },
    
    setTemplate: function(template_id){
        var rq = new Request.HTML({
            'onComplete':function(t,e,h,j){
                this.element.empty();
                this.element.adopt(t);
                this.redraw();
            }.bind(this)
        }).get('/template_preview/'+template_id);
    },
    
    dump: function(){
        var fields = this.element.getElements('.tfield');
        var output = {};
        fields.each(function(item,index){
            output[item.get('id').replace('tfield_','')] = item.get('html');
        });
        this.outputField.set('value', JSON.encode(output));
    },
    
    redraw: function(){
        this.element.getElements('.tfield').each(function(elem,index){
            field_id = elem.get('id').replace('tfield_','');
            elem.empty();
            elem.set('html','None');
            if (field_id in this.mapping){
                elem.set('html',this.mapping[field_id]);
            }
            elem.addEvent('click',function(e){
                var current = this.values.indexOf(elem.get('html'));
                var next = (current+1) % this.values.length;
                elem.set('html',this.values[next]);
                this.fieldChanged(elem);
            }.bind(this));
            elem.addEvents({
                'mouseover':function(e){$(e.target).addClass('hovered');},
                'mouseout':function(e){$(e.target).removeClass('hovered');}
            })
        },this);
    },
    
    /**
     * Changes all fields with the same name, so that same value is selected
     * across all identical fields.
     */
    fieldChanged: function(field){
        var selectedValue = field.get('html');
        var sameFields = $$('.tfield[id='+field.get('id')+']');
        sameFields.set('html',selectedValue);
        this.dump();
    }
});


var StudyClient = new Class({
    Implements: [Options],
    options:{
        stacksize: 4
    },
    
    initialize: function(id, box_id, options){
        this.element = $(id);
        this.box_id = box_id
        this.cardstack = [];
        this.cardContainer = this.element.getElement('.card-container');
        this.element.getElement('.buttons').adopt(new Element('a',{
            'url':'#',
            'html':'correct',
            'class':'button-correct',
            'events':{
                'click':function(e){
                    this.sendCard(true);
                    return false;
                }.bind(this)
            }
        }));
        this.element.getElement('.buttons').adopt(new Element('a',{
            'url':'#',
            'html':'wrong',
            'class':'button-wrong',
            'events':{
                'click':function(e){
                    this.sendCard(false);
                    return false;
                }.bind(this)
            }
        }));
        this.currentCard = null;
        this.cardRequest = new Request.HTML({
            url:'/next_card/'+this.box_id,
            method:'get',
            noCache:true
        });
        this.cardRequest.addEvent('success',function(t,e,h,js){
            this.cardstack.push(t);
            this.update();
        }.bind(this));
        this.update();
    },
    
    update: function(){
        if (this.cardstack.length < this.options.stacksize){
            this.cardRequest.send();
        }
        if (this.currentCard === null){
            this.popCardStack();
        }
    },
    
    popCardStack: function(){
        if (this.cardstack.length == 0) {
            this.currentCard = null;
            return;
        };
        var nextCard = this.cardstack.pop();
        this.cardContainer.empty();
        var cardInfo = this.element.getElement('.card-info').empty();
        var boxInfo = this.element.getElement('.box-info').empty();
        this.cardContainer.adopt(nextCard);
        this.currentCard = this.cardContainer.getElement('.card');
        cardInfo.adopt(this.cardContainer.getElement('.card-info').show());
        boxInfo.adopt(this.cardContainer.getElement('.box-info').show());
        var front_slide = new Fx.Slide(this.currentCard.getElement('div.front'));
        var back_slide = new Fx.Slide(this.currentCard.getElement('div.back'));
        this.currentCard.getElement('p.flip').show();
        back_slide.hide();
        this.currentCard.store('front_slide',front_slide);    
        this.currentCard.store('back_slide',back_slide);
        this.currentCard.addEvent('click',this.flipCard.create({'event':true,'bind':this}));
        KeyBinder.bindKey('flip',{'keys': 'space',
                        'description':'flip the current card',
                        'handler':this.flipCard.create({'event':true,'bind':this})
        });
        KeyBinder.bindKey('flip',{'keys': 'enter',
                        'description':'flip the current card',
                        'handler':this.flipCard.create({'event':true,'bind':this})
        });
    },
    
    flipCard: function(){
        if(this.currentCard === null){return;}
        
        this.currentCard.retrieve('front_slide').toggle();
        this.currentCard.retrieve('back_slide').toggle();
        KeyBinder.bindKey('flip',{'keys': 'enter',
                        'description':'answered correctly',
                        'handler':this.sendCard.create({arguments:true,bind:this})
        });
        KeyBinder.bindKey('flip',{'keys': 'space',
                        'description':'answered wrong',
                        'handler':this.sendCard.create({arguments:false,bind:this})
        });
    },
    
    sendCard: function(correct){
        if (this.currentCard === null){return;}
        this.cardContainer.getElement('form .correct').set('value', String(correct))
        this.cardContainer.getElement('form').send()
        if(correct){
            this.element.getElement('.button-correct').highlight('#AEE36D')
        } else {
            this.element.getElement('.button-wrong').highlight('#BF6F8C')
        }
        this.cardContainer.empty();
        this.element.getElement('.card-info').empty();
        this.element.getElement('.box-info').empty();
        this.currentCard = null;
        this.update();
    }
});

var KeyBinder = new new Class({
    initialize: function(){
        this.element = null;
        this.keyboard = new Keyboard({
            defaultEventType: 'keydown'
        });
        this.shortcuts = [];
    },
    
    setInterface: function(id){
        this.element = $(id);
        this.element.adopt(new Element('ul'));  
        this.redraw();  
    },
    
    bindKey: function(name, shortcut){
        var remaining = []
        this.shortcuts.each(function(item, index){
            if ( item.keys == shortcut.keys ){
                this.keyboard.removeEvent(item.keys, item.handler);
            } else {
                remaining.push(item);
            }
        },this);
        this.shortcuts = remaining;
        this.keyboard.addEvent(shortcut.keys, shortcut.handler);
        this.shortcuts.push(shortcut);
        this.redraw();
    },
    
    redraw: function(){
        if (this.element === null){return;}
        var shortcutList = this.element.getElement('ul');
        shortcutList.empty();
        this.shortcuts.each(function(item,index){
            key = new Element('span',{
                'class':'key',
                'html':item.keys});
            li = new Element('li',{
                'html':item.description});
            shortcutList.adopt(li);    
            li.adopt(key);
        });
    }
});