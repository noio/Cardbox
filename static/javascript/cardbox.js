/** CLASSES **/
var BrowseTable = new Class({
    Implements: [Options,Events],
    options:{
        kind: null,
        actions: ['select'],
        filters: []
    },

    initialize: function(id, options){
        this.setOptions(options);
        this.element = $(id);
        this.element.addClass('browser');
        this.element.set('spinner',{message:'Wait a moment...'});
        this.element.adopt(new Element('table'));
        this.table = new HtmlTable(this.element.getElement('table'),{
            'selectable':true,
            'sortable':true,
            'sortReverse':true,
            'allowMultiSelect':false
        });
    },
    
    update: function(opts){
        this.setOptions(opts);
        this.refresh();
    },
    
    refresh: function(){
        this.element.spin()
        var dataRequest = new Request.JSON({
            url: "/browse_data/"+this.options.kind.toLowerCase(), 
            onSuccess: function(data){
                this.data = data;
                this.redraw();
            }.bind(this)
        }).get(this.options.filters);
    },
    
    redraw: function(){
        this.element.unspin();
        this.table.empty();
        var headers = this.data.headers.slice(2);
        headers.unshift('view');
        headers = this.options.actions.concat(headers);
        this.table.setHeaders(headers);
        this.data.rows.each(function(row,idx){
            this.addRow(row);
        },this);
    },
    
    getNamedRowData: function(id){
        var rd = this.getRowData(id);
        return rd.associate(this.data.headers);
    },
    
    getRowData: function(id){
        return this.element.getElement('tr[id='+id+']').retrieve('rowData');
    },
    
    addRow: function(rowData){
        if (this.getRowIds().contains(rowData[0])) return
        var tr = rowData.slice(2);
        var viewLink = new Element('a',{'href':rowData[1],
                                        'target':'_blank',
                                        'html':'view'})
        tr.unshift(viewLink);
        this.options.actions.each(function(a,idx){
            var action = new Element('a',{'href':'#',
                                          'html':a,
                                          'class':'action_'+a})
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

var MappingSelector = new Class({
    
    initialize: function(id, field){
        this.element = $(id);
        this.element.addClass('mapper');
        this.outputField = $(field);
        this.mapping = JSON.decode(this.outputField.get('value'))
        if (this.mapping == null) this.mapping = {}
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
        }).get('/template_preview/'+template_id)
    },
    
    dump: function(){
        var fields = this.element.getElements('select');
        var output = new Object;
        fields.each(function(item,index){
            output[item.get('name').replace('f_','')] = item.getSelected()[0].get('value');
        });
        this.outputField.set('value', JSON.encode(output));
    },
    
    redraw: function(){
        this.element.getElements('.tfield').each(function(item,index){
            item.getElements('select').dispose();
            field_id = item.get('id').replace('tfield_','');
            select = new Element('select',{
                'id':'id_'+field_id+'_'+index,
                'name':'f_'+field_id
            });
            select.addEvent('change',this.fieldChanged.create({
                'bind':this,
                'event':true,
                'arguments':select
            }));
            select.adopt(this.getSelectOptions(field_id));
            item.adopt(select);
        },this);
    },
    
    /**
     * Changes all fields with the same name, so that same value is selected
     * across all identical fields.
     */
    fieldChanged: function(event,select){
        var fieldName = select.get('name');
        var selectedValue = select.getSelected()[0].get('value');
        var opts = $$('select[name='+fieldName+'] option[value='+selectedValue+']');
        opts.set('selected',true);
        this.dump();
    },
    
    getSelectOptions: function(field){
        var opts = this.values.map(function(item,index){
            var selected = (this.mapping[field] == item)
            return new Element('option',{'value':item,
                                         'html':item,
                                         'selected':selected});
        }.bind(this));
        return opts
    }
});

/** FUNCTIONS **/
/** 
 * Initializes the studying of cards. Fills box by first card in queue
 */
function startStudy(box_id){
    window.box_id = box_id;
    $('card-to-study').spin({'message':"Loading cards..."});
    extendCardQueue();
}

/**
 * Adds request to receive a new card. Repeats until queue is full.
 */
function extendCardQueue(){
    if (typeof window.cardqueue=='undefined'){
        window.cardqueue = [];
    }
    if (window.cardqueue.length < 4){
        var rq = new Request.HTML().get('/next_card/'+window.box_id);
        rq.addEvent('success',function(t,e,h,js){
            window.cardqueue.push(t);
            if( $('card-to-study').getElements('.card').length == 0 ){
                shiftCardQueue();
            }
            extendCardQueue();
        });
    }
}

/**
 * Replaces currend card by head in queue. Does not extend queue
 */
function shiftCardQueue(){
    if (window.cardqueue.length == 0) return;
    nxt = window.cardqueue.shift();
    $('card-to-study').empty();
    $('card-meta').empty();
    $('box-meta').empty();
    $('card-to-study').unspin();
    $('card-to-study').adopt(nxt);
    $('card-meta').adopt($$('#card-to-study .card-meta > *'));
    $('box-meta').adopt($$('#card-to-study .box-meta > *'));
    activateCard($$('#card-to-study .card')[0]);
    extendCardQueue();
}

/**
 * Folds given card into mootools Fx.Slide flippable cards,
 * highlights them and binds keys to flip 
 */
function activateCard(card){
    var front_slide = new Fx.Slide(card.getElement('div.front'));
    var back_slide = new Fx.Slide(card.getElement('div.back'));
    card.getElement('p.flip').show();
    back_slide.hide();
    card.store('front_slide',front_slide);    
    card.store('back_slide',back_slide);
    card.addEvent('click',function(){
        flipCard(card);
    });
    bindKey('flip',{'keys': 'space',
                    'description':'flip the current card',
                    'handler':flipCard.create({arguments:card})
    });
    bindKey('flip',{'keys': 'enter',
                    'description':'flip the current card',
                    'handler':flipCard.create({arguments:card})
    });
}

/**
 * Flips current card
 */
function flipCard(card){
    card.retrieve('front_slide').toggle();
    card.retrieve('back_slide').toggle();
    if($$('#card-to-study').length > 0){
        bindKey('flip',{'keys': 'enter',
                        'description':'answered correctly',
                        'handler':sendCard.create({arguments:true})
        });
        bindKey('flip',{'keys': 'space',
                        'description':'answered wrong',
                        'handler':sendCard.create({arguments:false})
        });
    }
}

/**
 * Submits the form to record correct/wrong score of card
 */
function sendCard(correct){
    if (window.cardqueue.length == 0) return;
    $$('#card-to-study form .correct').set('value', String(correct))
    $$('#card-to-study form').send()
    if(correct){
        $$('.button-correct').highlight('#AEE36D')
    } else {
        $$('.button-wrong').highlight('#BF6F8C')
    }
    shiftCardQueue();
}

function bindKey(name, shortcut){
    var remaining = []
    window.keyboardShortcuts.each(function(item, index){
        if ( item.keys == shortcut.keys ){
            window.keyboard.removeEvent(item.keys, item.handler);
        } else {
            remaining.push(item);
        }
    });
    window.keyboardShortcuts = remaining;
    window.keyboard.addEvent(shortcut.keys, shortcut.handler);
    window.keyboardShortcuts.push(shortcut);
    var shortcutList = $$('#shortcuts ul')[0];
    shortcutList.empty();
    window.keyboardShortcuts.each(function(item,index){
        key = new Element('span',{
            'class':'key',
            'html':item.keys});
        li = new Element('li',{
            'html':item.description});
        shortcutList.adopt(li);    
        
        li.adopt(key);
    });
}

/** AUTOLOAD **/
window.addEvent('domready',function(){
    window.keyboard = new Keyboard({
        defaultEventType: 'keydown', 
    });
    window.keyboardShortcuts = []
});

