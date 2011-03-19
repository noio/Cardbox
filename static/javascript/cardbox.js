/** CLASSES **/

/**
 * Ribbon is an expanding navigation menu, using hierarchical 
 * horizontal bars.
 */
var Ribbon = new Class({
    Implements: [Options],
    options:{
        'delay':2000
    },
    
    initialize: function(id, options){
        this.navbar = $(id);
        this.setOptions(options);
        this.submenus = [];
        this.navbar.getChildren('li').each(function(li, idx){
            li.addClass('main');
            li.getElement('a').addClass('main')
            var ul = li.getElement('ul');
            if (ul){
                var div = new Element('div').inject(ul, 'before');
                var submenu = new Element('div',{'class':'submenu'}).inject(div).grab(ul);
                //Fix width of submenu
                var totalWidth = 0;
                ul.setStyle('width','1000px');
                ul.getElements('li').each(function(innerLi,i2){
                    var size = innerLi.getComputedSize({'styles':['padding','border','margin']})
                    totalWidth += size.totalWidth;
                });
                ul.setStyle('width',null);
                ulSize = ul.getComputedSize();
                totalWidth += (ulSize['border-left-width'] + ulSize['border-right-width']);
                totalWidth = Math.ceil(totalWidth+3);
                div.position({
                     'relativeTo':li,
                     'position':'centerBottom',
                     'edge':'centerTop'
                });
                div.setStyle('width',totalWidth+'px');
                submenu.setStyle('width',totalWidth+'px');
                //Set tweens
                submenu.set('slide', {'duration':200});
                submenu.set('tween', {'duration':200})
                submenu.slide('hide');
                this.submenus.push(submenu);
                //Add events to open and close submenus
                var anchors = li.getElements('a');
                anchors.addEvent('mouseover',function(e){
                    $(e.target).addClass('focused');
                    this.open(submenu);
                }.bind(this));
                anchors.addEvent('mouseout',function(e){
                    $(e.target).removeClass('focused');
                    this.delayClose();
                }.bind(this));
            };
        }.bind(this));
        var navbarTips = new Tips(this.navbar.getElements('ul a'), {
            'fixed':true,
            'offset':{'x':0,'y':50},
            'text':'',
            'showDelay':400,
            'hideDelay':0,
            'onShow':function(tt,h){
                tt.set('tween',{'duration':200});
                tt.fade('hide');
                tt.fade('in');
            },
            'onHide':function(tt,h){
                tt.fade('hide');
            }
        });
    },
    
    open: function(submenu){
        this.submenus.each(function(sm,i){
            if (sm == submenu && !sm.get('slide').open){
                sm.slide('in');
                sm.fade('in');
            }
            if (sm != submenu && sm.get('slide').open){
                sm.slide('out');
                sm.fade('out');
            }
        });
        if (!!(this.timer)){
            clearTimeout(this.timer);
        }
    },
    
    delayClose: function(){
        if (!!(this.timer)){
            clearTimeout(this.timer);
        }
        this.timer = this.closeAll.delay(this.options.delay, this);
    },
    
    closeAll: function(){
        this.submenus.each(function(s,i){
            s.slide('out');
            s.fade('out');
        });
    }
})



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

    setFactsheet: function(list_id){
        var rq = new Request.JSON({
            'onComplete':function(json, text){
                this.setValues(json.columns);
                this.redraw();
            }.bind(this)
        }).get('/list/'+list_id+'/json');
    },
    
    setTemplate: function(template_id){
        var rq = new Request.HTML({
            'update':this.element,
            'onComplete':function(t,e,h,j){
                this.redraw();
            }.bind(this)
        }).get('/template/'+template_id+'/preview');
    },
    
    setValues: function(values){
        this.values = ['None'].combine(values.erase(''));
        // Remove mapping entries that don't occur in values.
        for (field_id in this.mapping){
            if (!this.values.contains(this.mapping[field_id])){
                delete this.mapping[field_id];
            }
        }
        this.redraw();
    },
    
    dump: function(){
        var fields = this.element.getElements('.tfield');
        var output = {};
        fields.each(function(item,index){
            output[item.get('id').replace('tfield_','')] = item.get('html');
        });
        this.mapping = output;
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
                var nextVal = this.values[next];
                elem.set('html',nextVal);
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

var ListEditor = new Class({
    Implements: [Options],
    options:{
        fieldNamePrefix:'list'
    },

    initialize: function(table,options){
        this.table = document.id(table);
        this.setOptions(options);
        this.checkEmpty();
        this.wrapCells();
        this.setFieldNames();
        this.checkExpansion();
    },
    
    wrapCells: function(){
        var cells = this.table.getElements('th,td');
        cells.each(function(cell){
            if (!cell.getElement('input')){
                var value = cell.get('html');
                cell.set('html','<input type="text" value="'+value+'">');
            }
        },this);
    },
    
    setFieldNames: function(){
        var headers = this.table.getElements('th');
        var prefix  = this.options.fieldNamePrefix
        headers.each(function(header, i){
            header.getElement('input').setProperty('name', prefix+'-header-'+i)
        },this);
        var rows = this.table.getElements('tbody tr');
        rows.each(function(row, i){
            var cells = row.getElements('td');
            cells.each(function(cell, j){
                cell.getElement('input').setProperty('name', prefix+'-row-'+i+'-col-'+j);
            },this);
        },this);
    },
    
    checkEmpty: function(){
        var cells = this.table.getElements('th,td');
        if (cells.length == 0){
            var headerRow = Element('tr').adopt([Element('th'),Element('th')]);
            this.table.getElement('thead').adopt(headerRow);
            for(var i=0; i<3; i++){
                var row = Element('tr').adopt([Element('td'),Element('td')]);
                this.table.getElement('tbody').adopt(row);
            }
        }
    },
    
    checkExpansion: function(){
        var lastRow = this.table.getElements('tr').getLast().getElements('td')
        var lastRowUsed = lastRow.some(function(td){
            return td.getElement('input').getProperty('value');
        });
        if (lastRowUsed) {
            var newRow = Element('tr');
            newRow.adopt(lastRow.map(function(i){return new Element('td');}));
            this.table.getElement('tbody').adopt(newRow);
            this.wrapCells();
            this.setFieldNames();
        }
    }
})


var StudyClient = new Class({
    Implements: [Options],
    options:{
        stacksize: 5,
        stackview: null,
    },
    
    initialize: function(id, box_id, options){
        this.setOptions(options);
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
            url:'/box/'+this.box_id+'/next_card',
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
        if (this.currentCard === null){
            this.popCardStack();
        }
        if (this.cardstack.length < this.options.stacksize){
            this.cardRequest.send();
        }
        this.drawStack()
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
        back_slide.hide();
        this.currentCard.store('front_slide',front_slide);    
        this.currentCard.store('back_slide',back_slide);
        this.currentCard.addEvent('click',this.flipCard.bind(this));
        KeyBinder.bindKey('flip',{'keys': 'space',
                        'description':'flip the current card',
                        'handler':this.flipCard.bind(this)
        });
        KeyBinder.bindKey('flip',{'keys': 'enter',
                        'description':'flip the current card',
                        'handler':this.flipCard.bind(this)
        });
    },
    
    drawStack: function(){
        if(!(this.options.stackview === null)){
            var s = $(this.options.stackview);
            s.empty();
            ul = new Element('ul').inject(s);
            this.cardstack.each(function(card, idx){
                ul.adopt(new Element('li'));
            }.bind(this));
        }
    },
    
    flipCard: function(){
        if(this.currentCard === null){return;}
        
        this.currentCard.retrieve('front_slide').toggle();
        this.currentCard.retrieve('back_slide').toggle();
        KeyBinder.bindKey('flip',{'keys': 'enter',
                        'description':'answered correctly',
                        'handler':this.sendCard.pass(true,this)
        });
        KeyBinder.bindKey('flip',{'keys': 'space',
                        'description':'answered wrong',
                        'handler':this.sendCard.pass(false,this)
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

var ModalBox = new Class({
    Implements: [Options],
    options:{
        title: ''
    },
    
    initialize: function(id, options){
        this.setOptions(options);
        this.element = $(id);
        //this.element.addClass('content');
        this.modal = new Element('div',{'class':'modal'})
        var inner = new Element('div',{'class':'inner'});
        inner.wraps(this.element);
        this.modal.wraps(inner);
        inner.addEvent('click',function(e){
            e.stopPropagation();
        });
        this.modal.addEvent('click',function(e){
            e.stop();
            this.modal.fade('out');
        }.bind(this));
        this.modal.fade('hide');
    },
    
    show: function(){
        this.modal.fade('in');
    },
    
    hide: function(){
        this.modal.fade('out');
    }
})

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
