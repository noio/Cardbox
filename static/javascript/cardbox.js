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
        this.table.getElements('a.button').destroy();
        var lastheader = this.table.getElement('thead tr th:last-child');
        var addColumn = new Element('a',{
            'href':'#','class':'button add-column',
            'events':{
                'click':function(event){
                    event.preventDefault();
                    this.addColumn();
                }.bind(this)
            }
        }).grab(new Element('span',{'class':'icon-add','html':'Add Column'}));
        lastheader.grab(addColumn);
        var rows = this.table.getElements('tbody tr').slice(0,-1);
        rows.each(function(row,i){
            var first = row.getElement('td:first-child');
            var last  = row.getElement('td:last-child');
            var removeButton = Element('a',{
                'href':'#', 'class':'button remove-row',
                'events':{
                    'click':function(event){
                        event.preventDefault();
                        new Fx.Tween(row, {'property':'opacity'}).start(1,0).chain(
                            row.destroy.bind(row)
                        );
                    }
                }
            }).grab(new Element('span',{'class':'icon-remove','html':'Remove Row'}));
            var addButton = new Element('a',{
                'href':'#', 'class':'button add-row',
                'events':{
                    'click':function(event){
                        event.preventDefault();
                        this.newRow().inject(row,'before').fade('hide').fade('in');
                        this.update();
                    }.bind(this)
                }
            }).grab(new Element('span',{'class':'icon-add','html':'Add Row'}));
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
            var headerRow = this.table.getElement('thead tr').adopt([new Element('th'),new Element('th')]);
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
        new Element('div.draggers').inject(this.element.getElement('.card-container'),'before');
        // Add event for template changes
        var t = this;
        this.element.getElement('input[name=cardset-template]').addEvent('change',function(event){
            t.setTemplate(this.get('value'));
            t.render();
        });
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
        // Update the suggested title
        this.setSuggestedTitle()
    },
    
    setSuggestedTitle: function(){
        if (this.templateFields === undefined) return;
        // Get the most important field + what it's mapped to.
        var f = this.templateFields.front.map(function(f){return this.mapping[f]}.bind(this));
        var b = this.templateFields.back.map(function(f){return this.mapping[f]}.bind(this));
        b = b.filter(function(field){return !f.contains(field);});
        f = f.pick();
        b = b.pick();
        // Set title only if current title empty or also autoset.
        var currentTitle = this.element.getElement('input[name=cardset-title]').get('value')
        if (f && b && (!currentTitle || currentTitle.contains(' - ')) ){
            var t = f + ' - ' + b
            this.element.getElement('input[name=cardset-title]').set('value',t)
        }
    },
    
    getFieldName: function(field){
        return field.getProperty('class')
            .split(' ').filter(function(f){
                return f.contains('tfield_')
            })[0].replace('tfield_','');
    },
    
    setMapping: function(fieldName, varName){
        if (varName){
            this.mapping[fieldName] = varName;
        } else {
            delete this.mapping[fieldName];
        }
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
        
        var jr = new Request.JSON({
            'url':'/template/'+template+'/fields',
            'onSuccess':function(j,t){
                this.templateFields = j;
            }.bind(this)
        }).get()
    }
    
});


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
