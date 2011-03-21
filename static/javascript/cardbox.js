/** CLASSES **/


/** Table for editing list values. Automatically expands
    when all rows have been used.
 **/
var ListEditor = new Class({
    Implements: [Options],
    options:{
        fieldNamePrefix:'list'
    },

    initialize: function(table,options){
        this.table = document.id(table);
        if (!this.table.get('tag') == 'table'){
            this.table = this.table.getElement('table');
        }
        this.setOptions(options);
        this.checkEmpty();
        this.wrapCells();
        this.checkExpansion();
        this.update();
    },
    
    getColumnNames: function(){
        return this.table.getElements('th input').get('value');
    },
    
    getRows: function(){
        rows = [];
        columns = this.getColumnNames();
        this.table.getElements('tbody tr').each(function(tr){
            var row = tr.getElements('td input').get('value');
            rows.push(row.associate(columns));
        });
        return rows;
    },
    
    update: function(){
        this.wrapCells();
        this.setFieldNames();
        this.addButtons();
    },
    
    newRow: function(){
        var tr = new Element('tr');
        var tds = this.table.getElements('th').map(function(th){return new Element('td')},this);
        return tr.adopt(tds);
    },
    
    addColumn: function(){
        this.table.getElement('thead tr').grab(new Element('th'));
        this.table.getElements('a.button').destroy();
        this.table.getElements('tbody tr').each(function(row){
            row.grab(new Element('td'));
        });
        this.update();
    },
    
    wrapCells: function(){
        var cells = this.table.getElements('th,td');
        cells.each(function(cell){
            if (!cell.getElement('input')){
                var value = cell.get('html');
                var input = new Element('input',{type:'text', value:value})
                input.addEvent('change',this.checkExpansion.bind(this));
                cell.empty();
                cell.adopt(input);
            }
        },this);
    },
    
    addButtons: function(){
        var rows = this.table.getElements('tbody tr').slice(0,-1);
        rows = rows.filter(function(r){
            return !r.getElement('.button')
        });
        rows.each(function(row,i){
            var first = row.getElement('td:first-child');
            var last  = row.getElement('td:last-child');
            var removeButton = Element('a',{
                'html':'remove', 'href':'#', 'class':'button action-remove',
                'events':{
                    'click':function(event){
                        event.preventDefault();
                        new Fx.Tween(row, {'property':'opacity'}).start(1,0).chain(
                            row.destroy.bind(row)
                        );
                    }
                }
            });
            var addButton = new Element('a',{
                'html':'add', 'href':'#', 'class':'button action-add',
                'events':{
                    'click':function(event){
                        event.preventDefault();
                        this.newRow().inject(row,'before').fade('hide').fade('in');
                        this.update();
                    }.bind(this)
                }
            });
            first.grab(removeButton,'top');
            last.grab(addButton,'bottom');
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
            var headerRow = new Element('tr').adopt([new Element('th'),new Element('th')]);
            this.table.getElement('thead').adopt(headerRow);
            this.table.getElement('tbody').adopt(this.newRow());
            this.table.getElement('tbody').adopt(this.newRow());
        }
    },
    
    checkExpansion: function(){
        var lastRow = this.table.getElements('tr').getLast().getElements('td')
        var lastRowUsed = lastRow.some(function(td){
            return td.getElement('input').getProperty('value');
        });
        if (lastRowUsed) {
            this.newRow().inject(this.table.getElement('tbody')).fade('hide').fade('in');
            this.update();
        }
    }
})

/**
 * CardsetEditor allows users to select a mapping and edit 
 * the autosuggested name for the set.
 */
var CardsetEditor = new Class({
  
    initialize: function(element, listEditor){
        this.element = document.id(element);
        this.listEditor = listEditor;
        //Setup all data
        this.mapping   = JSON.decode(this.element.getElement('input[name=cardset-mapping]').value);
        this.samplerow = this.listEditor.getRows().getRandom();
        this.setTemplate(this.element.getElement('input[name=cardset-template]').value);
        // Add element for the draggers, render contents dynamically later.
        new Element('div.draggers').inject(this.element.getElement('.card-container'),'before')

        this.render();
    },
    
    render: function(){
        // Update the draggers
        var draggers = this.element.getElement('.draggers').empty()
        for (var v in this.samplerow){
            var dragger = new Element('div',{'html':this.samplerow[v]}).inject(draggers);
            dragger.grab(new Element('span.mapping',{'html':v}),'top')
        }
        // Update the card fields
        var fields = this.element.getElements('.card-container .tfield')
        fields.each(function(field){
            var fieldname  = this.getFieldName(field);
            field.empty();
            if (fieldname in this.mapping && this.mapping[fieldname] in this.samplerow){
                
                field.set('html',this.samplerow[this.mapping[fieldname]])
                field.grab(new Element('span.mapping',{'html':this.mapping[fieldname]}),'top')
            } else {
                field.set('html','&#160;&#160;')
            }
        },this);
        // Enable the draggers
        var editor = this;
        this.element.getElements('.draggers div').addEvent('mousedown',function(event){
            event.stop();
            var dragger = this;
            var clone = dragger.clone().setStyles(dragger.getCoordinates()).setStyles({
                'position': 'absolute'
            }).inject(document.body);
            
            var drag = new Drag.Move(clone, {
                'droppables': fields,
                
                onDrop: function(dragging, field){
                    dragging.destroy();
                    if (field != null){
                        editor.setMapping([editor.getFieldName(field)],dragging.getElement('.mapping').get('html'));
                        editor.render();
                    }
                },
                onEnter: function(dragging, field){
                    field.tween('background-color', '#98B5C1');
                },
                onLeave: function(dragging, field){
                    field.tween('background-color', '#FFF');
                },
                onCancel: function(dragging){
                    dragging.destroy();
                }
            });
            drag.start(event);
        });
    },
    
    getFieldName: function(field){
        return field.getProperty('class')
            .split(' ').filter(function(f){
                return f.contains('tfield_')
            })[0].split('_')[1];
    },
    
    setMapping: function(fieldName, varName){
        this.mapping[fieldName] = varName;
        this.element.getElement('input[name=cardset-mapping]').set('value',JSON.encode(this.mapping))
    },
    
    setTemplate: function(template){
        var hr = new Request.HTML({
            'url':'/template/'+template+'/view',
            'update':this.element.getElement('.card-container'),
            'onSuccess':function(t,e,h,j){
                this.render();
            }.bind(this)
        }).get();
    }
    
});


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
