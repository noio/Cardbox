
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
        var rows    = [];
        var columns = this.getColumnNames();
        var trs     = this.table.getElements('tbody tr:not(.removed)')
        trs.each(function(tr,i){
            if (i < trs.length - 1){
                var row = tr.getElements('td input').get('value');
                rows.push(row.associate(columns));
            }
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
        var tds = this.table.getElements('th:not(.button-cell)').map(function(th){return new Element('td')},this);
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
        var removedCells = this.table.getElements('tr.removed th,tr.removed td');
        removedCells.each(function(cell){
            if(cell.getElement('input')){
                cell.set('html',cell.getElement('input').get('value'));
            }
        });
        var cells = this.table.getElements('th,td');
        cells.each(function(cell){
            if (!cell.getElement('input')){
                var value = cell.get('html');
                var input = new Element('input',{type:'text', value:value});
                if (cell.getParent('.removed')){
                    input.set('readonly',"readonly");
                }
                input.addEvent('change',this.checkExpansion.bind(this));
                cell.empty();
                cell.adopt(input);
            }
        },this);
    },
    
    addButtons: function(){
        this.table.getElements('th.button-cell, td.button-cell').destroy();
        var firstheader = new Element('th.button-cell').inject(this.table.getElement('thead tr'),'top');
        var lastheader = new Element('th.button-cell').inject(this.table.getElement('thead tr'),'bottom');
        var addColumn = new Element('a',{
            'href':'#','class':'button add-column', 'tabindex':9000,
            'events':{
                'click':function(event){
                    event.preventDefault();
                    editor.addColumn();
                }
            }
        }).grab(new Element('span',{'class':'icon-add','html':'Add Column'}));
        lastheader.grab(addColumn);
        var rows = this.table.getElements('tbody tr')
        var editor = this;
        rows.each(function(row,i){
            var first = new Element('td.button-cell').inject(row,'top');
            var last  = new Element('td.button-cell').inject(row,'bottom');
            var removeIcon = new Element('span',{'class':(row.hasClass('removed')?'icon-undo':'icon-remove'),'html':'r'});
            
            var removeButton = Element('a',{
                'href':'#', 'class':'button remove-row', 'tabindex':9000,
                'events':{
                    'click':function(event){
                        event.preventDefault();
                        row.toggleClass('removed');
                        editor.update();
                    }
                }
            }).grab(removeIcon);
            var addButton = new Element('a',{
                'href':'#', 'class':'button add-row', 'tabindex':9000,
                'events':{
                    'click':function(event){
                        event.preventDefault();
                        editor.newRow().inject(row,'before').fade('hide').fade('in');
                        editor.update();
                    }
                }
            }).grab(new Element('span',{'class':'icon-add','html':'Add Row'}));
            if (i < rows.length - 1){
                first.grab(removeButton);
                last.grab(addButton);
            }
        },this);
    },
    
    setFieldNames: function(){
        var headers = this.table.getElements('th');
        var prefix  = this.options.fieldNamePrefix
        headers.each(function(header, i){
            header.getElement('input').setProperty('name', prefix+'-header-'+i)
        },this);
        var rows = this.table.getElements('tbody tr:not(.removed)');
        rows.each(function(row, i){
            var cells = row.getElements('td:not(.button-cell)');
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
        var lastRow = this.table.getElements('tr').getLast().getElements('td');
        var lastRowUsed = lastRow.some(function(td){
            return (td.getElement('input') && td.getElement('input').getProperty('value'));
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
  
    initialize: function(element, listEditor, nth){
        this.element = document.id(element);
        this.listEditor = listEditor;
        //Setup all data
        this.element.getElements('input[name=cardset-template-new]').set('name','cardset-template-'+(nth));
        this.mapping   = JSON.decode(this.element.getElement('input[name=cardset-mapping]').value);
        this.samplerow = this.listEditor.getRows().getRandom();
        if (this.currentTemplate()){
            this.fetchTemplate(this.currentTemplate());
        }
        // Add element for the draggers, render contents dynamically later.
        new Element('div.draggers.clearfix').inject(this.element.getElement('.card-container'),'before');
        // Add event for template changes
        this.element.getElement('.template-selector').slide('hide');
        this.element.getElements('.template-selector .template a').each(function(a){
            a.addEvent('click',function(event){
                event.preventDefault();
                a.getParent().getPrevious('input').set('checked',true);
                this.fetchTemplate(this.currentTemplate());
            }.bind(this));
        }.bind(this));
        this.element.getElement('.button.pick-template').addEvent('click',function(event){
            event.preventDefault();
            this.element.getElement('.template-selector').slide('toggle');
        }.bind(this));
        this.element.getElements('input[name=cardset-template]').addEvent('change',function(){
            this.fetchTemplate(this.currentTemplate());
            this.render();
        }.bind(this))
        // Render
        this.render();
    },
    
    
    render: function(){
        // Update the draggers
        var draggers = this.element.getElement('.draggers').empty()
        for (var v in this.samplerow){
            var dragger = new Element('div.dragger',{'html':this.samplerow[v]}).inject(draggers);
            dragger.grab(new Element('span.mapping',{'html':v}),'top')
        }
        // Update the card fields
        var fields = this.element.getElements('.card-container .tfield')
        fields.each(function(field){
            var fieldname  = this.getFieldName(field);
            field.empty();
            field.removeClass('empty');
            if (fieldname in this.mapping && this.mapping[fieldname] in this.samplerow){
                field.set('html',this.samplerow[this.mapping[fieldname]])
                var removeLink = new Element('a',{ 'href':'#', 
                    'events':{
                        'click':function(event){
                            event.preventDefault();
                            delete this.mapping[fieldname];
                            this.render();
                        }.bind(this)
                    }
                }).grab(new Element('span.icon-x',{'html':'x'}));
                field.grab(new Element('span.mapping',{'html':this.mapping[fieldname]+' '}).grab(removeLink));
            } else {
                field.set('html','EMPTY');
                field.addClass('empty');
            }
        },this);
        // Enable the draggers
        var editor = this;
        this.element.getElements('.draggers div').addEvent('mousedown',function(event){
            event.stop();
            var dragger = this;
            var clone = dragger.clone().setStyles(dragger.getCoordinates()).setStyles({
                'position': 'absolute','opacity':0.7
            }).inject(document.body);
            
            var drag = new Drag.Move(clone, {
                'droppables': fields,
                
                onDrop: function(dragging, field){
                    field.setStyle('background','inherit');
                    dragging.destroy();
                    if (field != null){
                        editor.setMapping([editor.getFieldName(field)],dragging.getElement('.mapping').get('html'));
                        editor.render();
                    }
                },
                onEnter: function(dragging, field){
                    field.setStyle('background', '#57A6CE');
                },
                onLeave: function(dragging, field){
                    field.setStyle('background', 'inherit');
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
    
    currentTemplate: function(){
        var selected = this.element.getElement('input[name^=cardset-template]:checked');
        if (selected){
            return selected.get('value')
        } else {
            return false;
        }
    },
    
    fetchTemplate: function(template){
        // Request the template's HTML
        var hr = new Request.HTML({
            'url':'/template/'+template+'/view',
            'update':this.element.getElement('.card-container'),
            'onSuccess':function(t,e,h,j){
                this.render();
            }.bind(this)
        }).get();
        
        // Request the fieldnames
        var jr = new Request.JSON({
            'url':'/template/'+template+'/fields',
            'onSuccess':function(j,t){
                this.templateFields = j;
            }.bind(this)
        }).get()
    }
    
});

var ModalBox = new Class({
    initialize: function(){
        // Create Elements
        this.wrapper   = new Element('div.modal');
        this.container = new Element('div.inner.boxed');
        this.overlay   = new Element('div.overlay');
        // Insert into DOM
        document.body.grab(this.overlay);
        this.wrapper.grab(this.container);
        document.body.grab(this.wrapper);
    },
    
    destroy: function(){
        this.wrapper.destroy();
        this.container.destroy();
        this.overlay.destroy();
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
        this.element   = $(id);
        this.box_id    = box_id
        this.cardstack = [];
        this.flipKeyboard  = new Keyboard({
            defaultEventType: 'keydown',
            events: {
                'space': this.flipCard.bind(this),
                'enter': this.flipCard.bind(this)
            }
        });
        this.sendKeyboard = new Keyboard({
             defaultEventType: 'keydown',
             events: {
                 'space': this.sendCard.pass(false,this),
                 'enter': this.sendCard.pass(true,this)
             }
        });
        this.flipKeyboard.activate();
        // Create Elements
        this.cardContainer = this.element.getElement('.card-container');
        var correctButton = this.element.getElement('.button.correct');
        var wrongButton = this.element.getElement('.button.wrong');
        // Add Events
        correctButton.addEvent('click',function(e){
            this.sendCard(true);
            return false;
        }.bind(this));
        wrongButton.addEvent('click',function(e){
            this.sendCard(false);
            return false;
        }.bind(this));
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
        document.body.set('tween', {duration: '30000', property: 'background-color'});
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
        cardInfo.adopt(this.cardContainer.getElement('.card-info').getChildren());
        boxInfo.adopt(this.cardContainer.getElement('.box-info').getChildren());
        var front_slide = new Fx.Slide(this.currentCard.getElement('div.front'));
        var back_slide = new Fx.Slide(this.currentCard.getElement('div.back'));
        back_slide.hide();
        this.currentCard.store('front_slide',front_slide);    
        this.currentCard.store('back_slide',back_slide);
        this.currentCard.addEvent('click',this.flipCard.bind(this));
        this.flipKeyboard.activate()
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
        this.sendKeyboard.activate()
    },
    
    sendCard: function(correct){
        if (this.currentCard === null){return;}
        this.cardContainer.getElement('form .correct').set('value', correct?'1':'0')
        this.cardContainer.getElement('form').send()
        if(correct){
            this.element.getElement('.button.correct').highlight('#AEE36D')
        } else {
            this.element.getElement('.button.wrong').highlight('#BF6F8C')
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
        console.log(shortcut)
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
