package com.popcap.framework.panel
{
   import com.popcap.framework.components.Alert;
   import com.popcap.framework.components.WorkCDLabel;
   import com.popcap.framework.components.toolTip.ToolTips;
   import com.popcap.framework.core.CommonModel;
   import com.popcap.framework.core.Config;
   import com.popcap.framework.core.Lang;
   import com.popcap.framework.events.MyEvent;
   import com.popcap.framework.managers.CursorManager;
   import com.popcap.framework.managers.DEventManager;
   import com.popcap.framework.managers.DataManager;
   import com.popcap.framework.managers.DaveManager;
   import com.popcap.framework.managers.ModuleManager;
   import com.popcap.framework.managers.PropItemsManager;
   import com.popcap.framework.managers.RemindManager;
   import com.popcap.framework.managers.SoundManager;
   import com.popcap.framework.managers.UIResourceManager;
   import com.popcap.framework.net.PVZNetConnection;
   import com.popcap.framework.uis.McButton;
   import com.popcap.framework.utils.Debug;
   import com.popcap.framework.utils.GardenUtils;
   import com.popcap.framework.utils.HashMap;
   import com.popcap.framework.utils.Reflection;
   import com.popcap.town.data.Data;
   import flash.display.DisplayObject;
   import flash.display.DisplayObjectContainer;
   import flash.display.InteractiveObject;
   import flash.display.MovieClip;
   import flash.display.Sprite;
   import flash.events.Event;
   import flash.events.EventDispatcher;
   import flash.events.MouseEvent;
   import flash.external.ExternalInterface;
   import flash.geom.Point;
   import flash.geom.Rectangle;
   import flash.text.TextField;
   import flash.text.TextFormat;
   
   public class ItemShopUI extends EventDispatcher
   {
      
      public static const CATEGORY_GARDEN:int = 0;
      
      public static const CATEGORY_STRENGTHEN:int = 1;
      
      public static const CATEGORY_TD:int = 2;
      
      public static const CATEGORY_HOUSE:int = 7;
      
      public static const CATEGORY_SHOP:int = 5;
      
      public static const CATEGORY_FUNCTION:int = 6;
      
      public static const CATEGORY_DECORATE:int = 3;
      
      public static const CATEGORY_POINTS:int = 8;
      
      public static const CATEGORY_COMMEND:int = 100;
      
      public static const STATUS_RANDOM:int = 11;
      
      public static const STATUS_LIMIT:int = 10;
      
      public static const STATUS_LIMES_DAY_POINT:int = 7;
      
      public static const STATUS_LIMES_DAY:int = 8;
      
      public static const STATUS_LIMES:int = 9;
      
      public static const STATUS_SPECIAL:int = 4;
      
      public static const STATUS_SPECIAL_POINT:int = 5;
      
      public static const STATUS_SPECIAL_DAY_POINT:int = 6;
      
      public static const STATUS_NEW:int = 3;
      
      public static const STATUS_HOT:int = 2;
      
      public static const STATUS_NORMAL:int = 1;
      
      public var ItemUnlockType:Array = [6,-1,-1,-1,-1,9,10,8];
      
      public var myItemSingleMap:HashMap;
      
      public var randomItemMap:HashMap;
      
      private var randomItemIdArr:Array;
      
      public var nextRefreshTime:String;
      
      public var curBuyItem:ItemShopListItem;
      
      private var skin:Sprite;
      
      private var prevBt:McButton;
      
      private var nextBt:McButton;
      
      private var backBt:McButton;
      
      private var addGemsBt:McButton;
      
      private var addMoneyBt:McButton;
      
      private var typeBt0:McButton;
      
      private var typeBt1:McButton;
      
      private var typeBt8:McButton;
      
      private var typeBt3:McButton;
      
      private var typeBt5:McButton;
      
      private var typeBt6:McButton;
      
      private var typeBt7:McButton;
      
      private var typeBt100:McButton;
      
      private var pageNumTxt:TextField;
      
      private var moneyTxt:TextField;
      
      private var gemsTxt:TextField;
      
      private var poinsTxt:TextField;
      
      private var dat:XML;
      
      private var datList:Array;
      
      private var itemDataListForCategory:Array;
      
      private var itemList:Array;
      
      private var refreshCDLabel:WorkCDLabel;
      
      private var itemCount:int = 6;
      
      private var curTypeIndex:int = 0;
      
      private var categoryOrderArr:Array;
      
      private var curPage:int;
      
      private var maxPage:int;
      
      private var pageSize:int = 6;
      
      private var daveMc:MovieClip;
      
      private var daveTxtMc:Sprite;
      
      private var bg:MovieClip;
      
      private var _curItemId:int = -1;
      
      private var _curCategory:int = -1;
      
      private var _tutorialItem:ItemShopListItem;
      
      public function ItemShopUI()
      {
         super();
         this.myItemSingleMap = new HashMap();
         this.randomItemMap = new HashMap();
         this.refreshCDLabel = new WorkCDLabel();
         this.refreshCDLabel.addEventListener(DEventManager.CDTIME_FINISHED,this.onRefreshItemCDFinished);
         this.categoryOrderArr = [CATEGORY_COMMEND,CATEGORY_POINTS,CATEGORY_GARDEN,CATEGORY_STRENGTHEN,CATEGORY_HOUSE,CATEGORY_SHOP,CATEGORY_FUNCTION,CATEGORY_DECORATE];
         DataManager.getInstance().addEventListener(MyEvent.BUILD_SUCCESS,this.addBuildItemToMap);
         DataManager.getInstance().addEventListener(MyEvent.PLANT_SUCCESS,this.addPlantItemToMap);
         this.init();
      }
      
      private function init() : void
      {
         var tWidth:int;
         var tHeight:int;
         var originPosX:int;
         var originPosY:int;
         var i:int;
         var item:ItemShopListItem = null;
         this.addGemsBt = new McButton(Lang.getLocalizationString(Lang.TIPS,Lang.PUBLIC,"ADD_GEMS"),"",SoundManager.TAP);
         this.addMoneyBt = new McButton("","",SoundManager.TAP);
         this.prevBt = new McButton("","",SoundManager.TAP);
         this.nextBt = new McButton("","",SoundManager.TAP);
         this.backBt = new McButton("","",SoundManager.BUTTON_CLICK);
         tWidth = 80;
         tHeight = 22;
         originPosX = 25;
         originPosY = 42;
         this.typeBt0 = new McButton("","",SoundManager.TAP);
         this.typeBt1 = new McButton("","",SoundManager.TAP);
         this.typeBt8 = new McButton("","",SoundManager.TAP);
         this.typeBt3 = new McButton("","",SoundManager.TAP);
         this.typeBt5 = new McButton("","",SoundManager.TAP);
         this.typeBt6 = new McButton("","",SoundManager.TAP);
         this.typeBt7 = new McButton("","",SoundManager.TAP);
         this.typeBt100 = new McButton("","",SoundManager.TAP);
         this.itemDataListForCategory = new Array();
         this.itemDataListForCategory[CATEGORY_GARDEN] = new Array();
         this.itemDataListForCategory[CATEGORY_STRENGTHEN] = new Array();
         this.itemDataListForCategory[CATEGORY_DECORATE] = new Array();
         this.itemDataListForCategory[CATEGORY_SHOP] = new Array();
         this.itemDataListForCategory[CATEGORY_FUNCTION] = new Array();
         this.itemDataListForCategory[CATEGORY_HOUSE] = new Array();
         this.itemDataListForCategory[CATEGORY_POINTS] = new Array();
         this.itemDataListForCategory[CATEGORY_COMMEND] = new Array();
         this.itemList = [];
         i = 0;
         while(i < this.itemCount)
         {
            item = new ItemShopListItem();
            this.itemList[i] = item;
            i++;
         }
         this.backBt.addActionEventListener(this.onClickBackBt);
         this.nextBt.addActionEventListener(this.changePage,1);
         this.prevBt.addActionEventListener(this.changePage,-1);
         this.typeBt100.addActionEventListener(this.setData,100);
         this.typeBt0.addActionEventListener(this.setData,CATEGORY_GARDEN);
         this.typeBt1.addActionEventListener(this.setData,CATEGORY_STRENGTHEN);
         this.typeBt8.addActionEventListener(this.setData,CATEGORY_POINTS);
         this.typeBt3.addActionEventListener(this.setData,CATEGORY_DECORATE);
         this.typeBt5.addActionEventListener(this.setData,CATEGORY_SHOP);
         this.typeBt6.addActionEventListener(this.setData,CATEGORY_FUNCTION);
         this.typeBt7.addActionEventListener(this.setData,CATEGORY_HOUSE);
         DataManager.getInstance().commonModel.addEventListener(CommonModel.MONEY_CHANGED,this.onMoneyChanged);
         DataManager.getInstance().commonModel.addEventListener(CommonModel.GEMS_CHANGED,this.onGemsChanged);
         DataManager.getInstance().commonModel.addEventListener(CommonModel.POINTS_CHANGED,this.onPointsChanged);
         this.addGemsBt.addActionEventListener(function():void
         {
            if(ExternalInterface.available)
            {
               ExternalInterface.call("controller.switchPage","order");
            }
         });
         this.dat = DataManager.getInstance().propItemXml;
         this.setMyItemSingleMap();
      }
      
      public function reset() : void
      {
         if(this.skin != null)
         {
            DataManager.getInstance().uiContainer.addChild(this.skin);
         }
         if(this.daveMc == null)
         {
            this.daveMc = Reflection.createMovieClip("crazyDave",DataManager.getInstance().swfManager.getUILibrary());
            this.daveTxtMc = Reflection.createSprite("dialogMc",DataManager.getInstance().swfManager.getUILibrary());
            this.daveMc.x = -60;
            this.daveMc.y = 170;
            this.daveTxtMc.y = 45;
            this.daveTxtMc.x = 3;
         }
         DaveManager.getInstance().setSkin(this.daveMc,this.daveTxtMc,Config.ITEM_SHOP_DAVE);
         DaveManager.getInstance().setAnimatorRate(3);
         DaveManager.getInstance().playAnimator(DaveManager.SHOW);
         DaveManager.getInstance().playAnimator(DaveManager.SHAKE);
      }
      
      private function skip2NextTutorialStep(param1:Event) : void
      {
         var _loc2_:int = 0;
         var _loc3_:Point = null;
         var _loc4_:Rectangle = null;
         var _loc5_:String = null;
         if(DataManager.getInstance().commonModel.tutorialStep == DataManager.TUTORIAL_STEP_BUY_HOUSE)
         {
            _loc2_ = CATEGORY_HOUSE;
         }
         if(DataManager.getInstance().commonModel.tutorialStep == DataManager.TUTORIAL_STEP_BUY_HOUSE && this._tutorialItem != null)
         {
            _loc3_ = this.skin.localToGlobal(new Point(this._tutorialItem.skin.x,this._tutorialItem.skin.y));
            _loc4_ = new Rectangle(_loc3_.x,_loc3_.y,this._tutorialItem.skin.width,this._tutorialItem.skin.height);
            _loc5_ = Lang.getLocalizationString(Lang.REMINDING,Lang.TUTORIAL,"CLICK_HOUSE_IN_SHOP");
            RemindManager.instance.hideLabelRemind();
            RemindManager.instance.hideHightLightArea();
            RemindManager.instance.showHightLightArea(_loc4_,true);
            RemindManager.instance.showLabelRemind(_loc5_,330);
         }
      }
      
      public function setSkin(param1:Sprite) : void
      {
         var _loc3_:ItemShopListItem = null;
         this.skin = param1;
         this.prevBt.setSkin(this.wrapSkinAsMovieClip(param1,"prevBt"));
         this.nextBt.setSkin(this.wrapSkinAsMovieClip(param1,"nextBt"));
         this.backBt.setSkin(this.wrapSkinAsMovieClip(param1,"backBt"));
         if(param1.getChildByName("moneyTxt") == null)
         {
            param1.addChild(this.makeTextField("moneyTxt",70,15,90,22,16,16777215,"right"));
         }
         if(param1.getChildByName("gemsTxt") == null)
         {
            param1.addChild(this.makeTextField("gemsTxt",248,14,105,22,16,16777215,"right"));
         }
         if(param1.getChildByName("pointsNumTxt") == null)
         {
            param1.addChild(this.makeTextField("pointsNumTxt",375,15,80,22,16,16777215,"left"));
         }
         if(param1.getChildByName("pageNumTxt") == null)
         {
            param1.addChild(this.makeTextField("pageNumTxt",360,490,80,22,14,16777215,"center"));
         }
         this.moneyTxt = param1.getChildByName("moneyTxt") as TextField;
         this.moneyTxt.mouseEnabled = false;
         this.gemsTxt = param1.getChildByName("gemsTxt") as TextField;
         this.gemsTxt.mouseEnabled = false;
         this.poinsTxt = param1.getChildByName("pointsNumTxt") as TextField;
         this.poinsTxt.mouseEnabled = false;
         if(param1.getChildByName("addGemsBt") == null)
         {
            var addGemsDummy:MovieClip = new MovieClip();
            addGemsDummy.name = "addGemsBt";
            param1.addChild(addGemsDummy);
         }
         if(param1.getChildByName("addMoneyBt") == null)
         {
            var addMoneyDummy:MovieClip = new MovieClip();
            addMoneyDummy.name = "addMoneyBt";
            param1.addChild(addMoneyDummy);
         }
         this.addGemsBt.setSkin(param1.getChildByName("addGemsBt") as MovieClip);
         this.addMoneyBt.setSkin(param1.getChildByName("addMoneyBt") as MovieClip);
         this.addMoneyBt.set("visible",false);
         var bgObj:DisplayObject = param1.getChildByName("mainBg");
         if(bgObj is MovieClip)
         {
            this.bg = bgObj as MovieClip;
         }
         else
         {
            var bgWrapper:MovieClip = new MovieClip();
            bgWrapper.name = "mainBgWrapper";
            bgWrapper.x = bgObj != null ? bgObj.x : 0;
            bgWrapper.y = bgObj != null ? bgObj.y : 0;
            if(bgObj != null)
            {
               bgObj.x = 0;
               bgObj.y = 0;
               param1.removeChild(bgObj);
               bgWrapper.addChild(bgObj);
            }
            param1.addChildAt(bgWrapper,0);
            this.bg = bgWrapper;
         }
         this.pageNumTxt = param1.getChildByName("pageNumTxt") as TextField;
         this.moneyTxt.text = "" + DataManager.getInstance().commonModel.money;
         this.gemsTxt.text = "" + DataManager.getInstance().commonModel.gems;
         this.poinsTxt.text = "" + DataManager.getInstance().commonModel.points;
         this.typeBt100.setSkin(this.wrapSkinAsMovieClip(this.skin,"tabBtn100"));
         this.typeBt0.setSkin(this.wrapSkinAsMovieClip(this.skin,"tabBtn0"));
         this.typeBt8.setSkin(this.wrapSkinAsMovieClip(this.skin,"tabBtn8"));
         this.typeBt1.setSkin(this.wrapSkinAsMovieClip(this.skin,"tabBtn1"));
         this.typeBt3.setSkin(this.wrapSkinAsMovieClip(this.skin,"tabBtn3"));
         this.typeBt5.setSkin(this.wrapSkinAsMovieClip(this.skin,"tabBtn5"));
         this.typeBt6.setSkin(this.wrapSkinAsMovieClip(this.skin,"tabBtn6"));
         this.typeBt7.setSkin(this.wrapSkinAsMovieClip(this.skin,"tabBtn7"));
         var _loc2_:int = 0;
         while(_loc2_ < this.itemCount)
         {
            _loc3_ = this.itemList[_loc2_];
            _loc3_.setSkin(this.prepareExternalItemSlot(param1,_loc2_ + 1));
            _loc2_++;
         }
         this.skin.getChildByName("moneyBg").addEventListener(MouseEvent.MOUSE_OVER,this.onMouseOverMoneyTxt);
         this.skin.getChildByName("moneyBg").addEventListener(MouseEvent.MOUSE_OUT,this.onMouseOutMoneyTxt);
         this.skin.getChildByName("gemsBg").addEventListener(MouseEvent.MOUSE_OVER,this.onMouseOverGemsTxt);
         this.skin.getChildByName("gemsBg").addEventListener(MouseEvent.MOUSE_OUT,this.onMouseOutGemsTxt);
      }
      
      private function onMouseOverMoneyTxt(param1:MouseEvent) : void
      {
         var _loc2_:String = Lang.getLocalizationString(Lang.TIPS,Lang.MAIN_SCREEN,"TOKEN_CONTENT");
         _loc2_ = _loc2_.replace("####","" + DataManager.getInstance().commonModel.money);
         ToolTips.instance.regToolTips(param1.currentTarget as InteractiveObject,Lang.getLocalizationString(Lang.TIPS,Lang.PUBLIC,"TOKEN"),_loc2_);
      }
      
      private function onMouseOutMoneyTxt(param1:MouseEvent) : void
      {
         ToolTips.instance.hideToolTips();
      }
      
      private function onMouseOutGemsTxt(param1:MouseEvent) : void
      {
      }
      
      private function onMouseOverGemsTxt(param1:MouseEvent) : void
      {
         var _loc2_:String = Lang.getLocalizationString(Lang.TIPS,Lang.MAIN_SCREEN,"GEM_CONTENT");
         _loc2_ = _loc2_.replace("####","" + DataManager.getInstance().commonModel.gems);
         ToolTips.instance.regToolTips(param1.currentTarget as InteractiveObject,Lang.getLocalizationString(Lang.TIPS,Lang.PUBLIC,"GEM"),_loc2_);
      }
      
      public function showItemShopUI(param1:int = -1, param2:int = -1) : void
      {
         this._curItemId = param1;
         this._curCategory = param2;
         this.sendPurchaseRecordC2S();
         this.setMyItemSingleMap();
      }
      
      private function initItemShopUI(param1:int = -1) : void
      {
         var _loc3_:Object = null;
         var _loc4_:int = 0;
         var _loc2_:ItemShopUI = DataManager.getInstance().itemShowUI;
         if(_loc2_ == null)
         {
            _loc2_ = new ItemShopUI();
         }
         _loc2_.setSkin(_loc2_.buildShopSkin());
         _loc2_.addEventListener(MyEvent.CLOSE,this.hideItemShopUI);
         DataManager.getInstance().uiContainer.addChild(_loc2_.getSkin());
         _loc2_.reset();
         if(this._curCategory > 0)
         {
            _loc2_.setData(this._curCategory);
         }
         else if(param1 > 0)
         {
            _loc3_ = DataManager.getInstance().propItemsConfigMap.getValue(String(param1));
            _loc4_ = int(_loc3_.category) == CATEGORY_TD || int(_loc3_.category) == CATEGORY_STRENGTHEN ? CATEGORY_STRENGTHEN : CATEGORY_GARDEN;
            _loc2_.setData(_loc4_);
         }
         else
         {
            _loc2_.setData();
         }
      }
      
      public function hideItemShopUI(param1:MyEvent = null) : void
      {
         if(DataManager.getInstance().moduleManager.curModule == ModuleManager.TOWN_MODULE)
         {
            DataManager.getInstance().bottomContainer.showFriendPanel();
         }
         var _loc2_:ItemShopUI = DataManager.getInstance().itemShowUI;
         if(_loc2_ != null && _loc2_.getSkin() != null)
         {
            if(DataManager.getInstance().uiContainer.contains(_loc2_.getSkin()))
            {
               DataManager.getInstance().uiContainer.removeChild(_loc2_.getSkin());
            }
         }
         DataManager.getInstance().dispatchEvent(new MyEvent(MyEvent.REMOVE_ITEM_SHOP));
      }
      
      public function getSkin() : Sprite
      {
         return this.skin;
      }
      
      public function dispose() : void
      {
         DataManager.getInstance().commonModel.removeEventListener(CommonModel.MONEY_CHANGED,this.onMoneyChanged);
         DataManager.getInstance().commonModel.removeEventListener(CommonModel.GEMS_CHANGED,this.onGemsChanged);
         this.prevBt.dispose();
         this.nextBt.dispose();
         this.backBt.dispose();
         this.typeBt0.dispose();
         this.typeBt1.dispose();
         this.typeBt3.dispose();
         this.typeBt5.dispose();
         this.typeBt6.dispose();
         this.typeBt7.dispose();
         this.typeBt8.dispose();
         this.typeBt100.dispose();
         var _loc1_:int = 0;
         while(_loc1_ < 8)
         {
            this.itemList[_loc1_].dispose();
            _loc1_++;
         }
      }
      
      public function setData(param1:int = 100) : void
      {
         this.initData();
         this.onClickTypeBy(param1);
      }
      
      private function onRefreshItemCDFinished(param1:Event) : void
      {
         this.stopCDTimeItemList();
         this.sendPurchaseRecordC2S();
      }
      
      private function setMyItemsListS2C(param1:Object) : void
      {
         if(param1 != null)
         {
            PropItemsManager.instace.resetMyPropMap(param1);
         }
         DataManager.getInstance().dispatchEvent(new MyEvent(MyEvent.REMOVE_ITEM_SHOP));
      }
      
      private function onPointsChanged(param1:MyEvent) : void
      {
         if(this.poinsTxt != null)
         {
            this.poinsTxt.text = "" + DataManager.getInstance().commonModel.points;
         }
      }
      
      private function onMoneyChanged(param1:MyEvent) : void
      {
         if(this.moneyTxt == null)
         {
            return;
         }
         this.moneyTxt.text = String(param1.data);
      }
      
      private function onGemsChanged(param1:MyEvent) : void
      {
         if(this.gemsTxt == null)
         {
            return;
         }
         this.gemsTxt.text = String(param1.data);
      }
      
      private function initData() : void
      {
         var _loc3_:Object = null;
         var _loc4_:Number = Number(NaN);
         var _loc5_:Number = Number(NaN);
         var _loc6_:String = null;
         var _loc7_:String = null;
         var _loc1_:Array = DataManager.getInstance().propItemsConfigMap.values();
         (this.itemDataListForCategory[CATEGORY_GARDEN] as Array).splice(0);
         (this.itemDataListForCategory[CATEGORY_STRENGTHEN] as Array).splice(0);
         (this.itemDataListForCategory[CATEGORY_DECORATE] as Array).splice(0);
         (this.itemDataListForCategory[CATEGORY_SHOP] as Array).splice(0);
         (this.itemDataListForCategory[CATEGORY_FUNCTION] as Array).splice(0);
         (this.itemDataListForCategory[CATEGORY_HOUSE] as Array).splice(0);
         (this.itemDataListForCategory[CATEGORY_COMMEND] as Array).splice(0);
         (this.itemDataListForCategory[CATEGORY_POINTS] as Array).splice(0);
         var _loc2_:int = 0;
         while(_loc2_ < _loc1_.length)
         {
            _loc3_ = _loc1_[_loc2_];
            if(Boolean(_loc3_.active) && int(_loc3_.category) >= 0)
            {
               _loc4_ = -1;
               _loc5_ = 1;
               if(String(_loc3_.onShelfTime) != "0" && String(_loc3_.offShelfTime) != "0")
               {
                  _loc6_ = String(_loc3_.onShelfTime);
                  _loc7_ = String(_loc3_.offShelfTime);
                  _loc4_ = GardenUtils.getLeftTime(_loc6_);
                  _loc5_ = GardenUtils.getLeftTime(_loc7_);
               }
               if(!(_loc4_ > 0 || _loc5_ < 0))
               {
                  if(String(_loc3_.category) == String(CATEGORY_GARDEN) || String(_loc3_.category) == String(CATEGORY_POINTS) || String(_loc3_.category) == String(CATEGORY_DECORATE) || String(_loc3_.category) == String(CATEGORY_FUNCTION) || String(_loc3_.category) == String(CATEGORY_SHOP) || String(_loc3_.category) == String(CATEGORY_HOUSE))
                  {
                     this.itemDataListForCategory[int(_loc3_.category)].push(_loc3_);
                     if(int(_loc3_.recommend) > 0)
                     {
                        (this.itemDataListForCategory[CATEGORY_COMMEND] as Array).push(_loc3_);
                     }
                  }
                  else if(String(_loc3_.category) == String(CATEGORY_STRENGTHEN) || String(_loc3_.category) == String(CATEGORY_TD))
                  {
                     this.itemDataListForCategory[CATEGORY_STRENGTHEN].push(_loc3_);
                     if(int(_loc3_.recommend) > 0)
                     {
                        (this.itemDataListForCategory[CATEGORY_COMMEND] as Array).push(_loc3_);
                     }
                  }
               }
            }
            _loc2_++;
         }
         (this.itemDataListForCategory[CATEGORY_GARDEN] as Array).sortOn(["status","featureShopOrder","name"],[Array.DESCENDING,Array.NUMERIC,Array.CASEINSENSITIVE]);
         (this.itemDataListForCategory[CATEGORY_STRENGTHEN] as Array).sortOn(["status","featureShopOrder","name"],[Array.DESCENDING,Array.NUMERIC,Array.CASEINSENSITIVE]);
         (this.itemDataListForCategory[CATEGORY_DECORATE] as Array).sortOn(["status","featureShopOrder","name"],[Array.DESCENDING,Array.NUMERIC,Array.CASEINSENSITIVE]);
         (this.itemDataListForCategory[CATEGORY_SHOP] as Array).sortOn(["status","featureShopOrder","name"],[Array.DESCENDING,Array.NUMERIC,Array.CASEINSENSITIVE]);
         (this.itemDataListForCategory[CATEGORY_HOUSE] as Array).sortOn(["status","featureShopOrder","name"],[Array.DESCENDING,Array.NUMERIC,Array.CASEINSENSITIVE]);
         (this.itemDataListForCategory[CATEGORY_FUNCTION] as Array).sortOn(["status","featureShopOrder","name"],[Array.DESCENDING,Array.NUMERIC,Array.CASEINSENSITIVE]);
         (this.itemDataListForCategory[CATEGORY_COMMEND] as Array).sortOn(["recommend","status","category","featureShopOrder","name"],[Array.DESCENDING,Array.NUMERIC,Array.NUMERIC,Array.CASEINSENSITIVE]);
      }
      
      public function sendPurchaseRecordC2S() : void
      {
         PVZNetConnection.getInstance().sendAndCall("services.I5005",this.setPurchaseListS2C);
      }
      
      public function onClickBackBt(param1:Event = null) : void
      {
         DaveManager.getInstance().hide();
         this.nextRefreshTime = null;
         this.refreshCDLabel.stopCD();
         this.stopCDTimeItemList();
         this.dispatchEvent(new MyEvent(MyEvent.CLOSE));
      }
      
      private function setPurchaseListS2C(param1:Object) : void
      {
         var _loc2_:String = null;
         if(param1 != null)
         {
            for(_loc2_ in param1.record)
            {
               if(param1.record[_loc2_] != null)
               {
                  DataManager.getInstance().myPurchaseItemsMap.put(_loc2_,param1.record[_loc2_]);
               }
            }
         }
         Debug.trace(" setPurchaseListS2C success ",DataManager.getInstance().myPurchaseItemsMap.size());
         PVZNetConnection.getInstance().sendAndCall("services.I5006",this.setRandomListS2C);
      }
      
      private function setRandomListS2C(param1:Object) : void
      {
         var _loc3_:String = null;
         var _loc4_:Object = null;
         this.randomItemMap.clear();
         this.randomItemIdArr = new Array();
         var _loc2_:Number = -1;
         if(this.nextRefreshTime != null)
         {
            _loc2_ = GardenUtils.getLeftTime(this.nextRefreshTime);
         }
         if(param1.list != null)
         {
            for(_loc3_ in param1.list)
            {
               _loc4_ = param1.list[_loc3_] as Object;
               if(null != _loc4_)
               {
                  this.randomItemMap.put(String(_loc4_.itemId),_loc4_);
                  this.randomItemIdArr.push(String(_loc4_.itemId));
               }
            }
         }
         if(null != param1.nextTime)
         {
            this.nextRefreshTime = param1.nextTime;
            this.refreshCDLabel.setCdTime(GardenUtils.getLeftTime(this.nextRefreshTime));
         }
         if(_loc2_ > 0)
         {
            this.initData();
            this.onClickTypeBy(0);
         }
         else
         {
            UIResourceManager.instance.openPanel(UIResourceManager.UI_RESOURCE_ITEM_SHOP,this.openItemShop);
         }
      }
      
      private function openItemShop() : void
      {
         this.initItemShopUI(this._curItemId);
         if(DataManager.getInstance().commonModel.tutorialStep == DataManager.TUTORIAL_STEP_BUY_HOUSE)
         {
            DaveManager.getInstance().hide();
            this.skip2NextTutorialStep(null);
         }
         else if((DataManager.getInstance().commonModel.tutorialStep & DataManager.TUTORIAL_STEP_SHOP_BT) <= 0)
         {
            DaveManager.getInstance().showDialog(Lang.getLocalizationString(Lang.NPC_DIALOGUE,Lang.ITEM_SHOP,"FIRST_COME"),SoundManager.CRAZY_DAVE_4);
         }
         else
         {
            DaveManager.getInstance().showDialog(Lang.getLocalizationString(Lang.NPC_DIALOGUE,Lang.ITEM_SHOP,"COME"),SoundManager.CRAZY_DAVE_4);
         }
         DataManager.getInstance().daveThread.pause = false;
      }
      
      private function setMyItemSingleMap() : void
      {
         var _loc3_:int = 0;
         var _loc4_:Array = null;
         var _loc5_:int = 0;
         var _loc6_:Object = null;
         var _loc7_:Array = null;
         var _loc8_:Array = null;
         var _loc9_:Object = null;
         var _loc10_:Object = null;
         var _loc11_:Object = null;
         var _loc1_:Array = DataManager.getInstance().myItemsMap.values();
         var _loc2_:int = 0;
         while(_loc2_ < _loc1_.length)
         {
            _loc4_ = _loc1_[_loc2_] as Array;
            if(null != _loc4_)
            {
               _loc5_ = 0;
               while(_loc5_ < _loc4_.length)
               {
                  _loc6_ = _loc4_[_loc5_];
                  this.myItemSingleMap.put(String(_loc6_.tid),_loc6_);
                  _loc5_++;
               }
            }
            _loc2_++;
         }
         if(Data.instance.cityDataObj != null)
         {
            _loc7_ = Data.instance.cityDataObj.buildings as Array;
            _loc8_ = Data.instance.cityDataObj.decorations as Array;
            if(_loc7_ != null)
            {
               _loc2_ = 0;
               while(_loc2_ < _loc7_.length)
               {
                  _loc9_ = _loc7_[_loc2_];
                  _loc3_ = 1;
                  _loc10_ = this.myItemSingleMap.get(String(_loc9_.tid));
                  if(_loc10_ == null)
                  {
                     _loc5_ = _loc2_ + 1;
                     while(_loc5_ < _loc7_.length)
                     {
                        if(String(_loc9_.tid) == String(_loc7_[_loc5_].tid))
                        {
                           _loc3_++;
                        }
                        _loc5_++;
                     }
                     this.myItemSingleMap.put(String(_loc9_.tid),{
                        "tid":_loc9_.tid,
                        "count":_loc3_
                     });
                  }
                  _loc2_++;
               }
            }
            if(_loc8_ != null)
            {
               _loc2_ = 0;
               while(_loc2_ < _loc8_.length)
               {
                  _loc11_ = _loc8_[_loc2_];
                  _loc3_ = int((String(_loc11_.layout).split(",") as Array).length);
                  this.myItemSingleMap.put(String(_loc11_.tid),{
                     "tid":_loc11_.tid,
                     "count":_loc3_
                  });
                  _loc2_++;
               }
            }
         }
      }
      
      private function addBuildItemToMap(param1:MyEvent) : void
      {
         var _loc2_:Object = null;
         var _loc3_:Object = null;
         if(param1.data != null && Boolean(param1.data.isBuy))
         {
            _loc2_ = param1.data as Object;
            _loc3_ = this.myItemSingleMap.get(String(_loc2_.id));
            if(_loc3_ != null)
            {
               _loc3_.count += 1;
            }
            else
            {
               _loc3_ = {
                  "tid":_loc2_.id,
                  "count":1
               };
            }
            this.myItemSingleMap.put(String(_loc2_.id),_loc3_);
         }
      }
      
      private function addPlantItemToMap(param1:MyEvent) : void
      {
         var _loc2_:Object = null;
         var _loc3_:Object = null;
         var _loc4_:Object = null;
         var _loc5_:Object = null;
         var _loc6_:String = null;
         if(param1.data != null)
         {
            _loc2_ = param1.data as Object;
            _loc3_ = this.myItemSingleMap.get(String(_loc2_.seedId));
            _loc4_ = DataManager.getInstance().myPurchaseItemsMap.get(String(_loc2_.seedId));
            if(_loc3_ != null)
            {
               _loc3_.count += 1;
            }
            else
            {
               _loc3_ = {
                  "tid":_loc2_.seedId,
                  "count":1
               };
            }
            this.myItemSingleMap.put(String(_loc2_.seedId),_loc3_);
            if(_loc4_ != null)
            {
               DataManager.getInstance().myPurchaseItemsMap.put(String(_loc2_.seedId),int(_loc4_) + 1);
            }
            else
            {
               DataManager.getInstance().myPurchaseItemsMap.put(String(_loc2_.seedId),1);
            }
            _loc5_ = DataManager.getInstance().propItemsConfigMap.get(String(_loc2_.seedId));
            if(_loc5_.status == DataManager.ITEM_STATUS_PURCHASE)
            {
               if(int(_loc4_) + 1 >= int(_loc5_.periodPurchaseCountLimit))
               {
                  _loc6_ = Lang.getLocalizationString(Lang.UI,Lang.ITEM_SHOP,"STORAGE_ERROR_DESC");
                  Alert.instance.show(DataManager.getInstance().uiContainer,_loc6_,null,null,null,true,false);
                  CursorManager.getInstance().hideMouse();
                  CursorManager.getInstance().setCursor(CursorManager.TYPE_DEFAULT);
                  DataManager.getInstance().bottomContainer.dispatchEvent(new MyEvent(MyEvent.MOUSE_BACK_DEFAULT));
               }
            }
         }
      }
      
      private function stopCDTimeItemList() : void
      {
         var _loc2_:ItemShopListItem = null;
         var _loc1_:int = 0;
         while(_loc1_ < this.itemCount)
         {
            _loc2_ = this.itemList[_loc1_] as ItemShopListItem;
            if(null != _loc2_)
            {
               _loc2_.resetCDTime();
            }
            _loc1_++;
         }
      }
      
      private function onClickTypeBy(param1:int) : void
      {
         var _loc6_:int = 0;
         var _loc7_:MovieClip = null;
         if(param1 != this.categoryOrderArr[this.curTypeIndex])
         {
            this.curTypeIndex = this.categoryOrderArr.indexOf(param1);
         }
         this.typeBt0.enabled = true;
         this.typeBt1.enabled = true;
         this.typeBt3.enabled = true;
         this.typeBt5.enabled = true;
         this.typeBt6.enabled = true;
         this.typeBt7.enabled = true;
         this.typeBt8.enabled = true;
         this.typeBt100.enabled = true;
         if(this._curCategory != -1)
         {
            this.typeBt0.enabled = this.typeBt1.enabled = this.typeBt3.enabled = this.typeBt5.enabled = this.typeBt6.enabled = this.typeBt7.enabled = this.typeBt8.enabled = this.typeBt100.enabled = false;
            _loc6_ = 0;
            while(_loc6_ < this.categoryOrderArr.length)
            {
               _loc7_ = this["typeBt" + this.categoryOrderArr[_loc6_]].getSkin();
               _loc7_.gotoAndStop(5);
               _loc6_++;
            }
         }
         this["typeBt" + param1].enabled = false;
         var _loc2_:MovieClip = this["typeBt" + param1].getSkin();
         _loc2_.gotoAndStop(4);
         var _loc3_:int = param1 * 4;
         this.prevBt.setFrameIndex([1,2,3,4]);
         this.nextBt.setFrameIndex([1,2,3,4]);
         this.curPage = 0;
         this.datList = this.itemDataListForCategory[param1];
         if(this.datList == null)
         {
            this.datList = [];
         }
         var _loc4_:int = int(this.datList.length);
         var _loc5_:* = _loc4_ - 1;
         while(_loc5_ >= 0)
         {
            if(this.randomItemIdArr.indexOf(String(this.datList[_loc5_].id)) == -1 && String(this.datList[_loc5_].status) == String(STATUS_RANDOM))
            {
               this.datList.splice(_loc5_,1);
            }
            _loc5_--;
         }
         this.maxPage = Math.ceil(this.datList.length / this.pageSize);
         this.changePage(0);
      }
      
      private function changePage(param1:int) : void
      {
         this.curPage += param1;
         if(this.curPage < 0)
         {
            this.curPage = 0;
         }
         else if(this.curPage >= this.maxPage - 1)
         {
            this.curPage = this.maxPage - 1;
         }
         this.refreshItemList();
      }
      
      private function takeAllItemsBack() : void
      {
         var _loc2_:ItemShopListItem = null;
         var _loc1_:int = 0;
         while(_loc1_ < this.itemCount)
         {
            _loc2_ = this.itemList[_loc1_] as ItemShopListItem;
            _loc2_.setVisible(false);
            _loc1_++;
         }
      }
      
      private function refreshItemList() : void
      {
         this.pageNumTxt.text = this.curPage + 1 + "/" + this.maxPage;
         var _loc1_:int = 0;
         var _loc2_:int = this.pageSize * this.curPage;
         while(_loc1_ < this.pageSize)
         {
            if(this.datList[_loc2_] != null)
            {
               if(DataManager.getInstance().commonModel.tutorialStep == DataManager.TUTORIAL_STEP_BUY_HOUSE && String(this.datList[_loc2_].id) == "701")
               {
                  this._tutorialItem = this.itemList[_loc1_];
               }
            }
            this.itemList[_loc1_].setData(this.datList[_loc2_]);
            _loc1_++;
            _loc2_++;
         }
      }
      
      private function makeTextField(name:String, x:int, y:int, w:int, h:int, size:int = 14, color:uint = 0, align:String = "left") : TextField
      {
         var tf:TextField = new TextField();
         tf.name = name;
         tf.x = x;
         tf.y = y;
         tf.width = w;
         tf.height = h;
         tf.selectable = false;
         tf.mouseEnabled = false;
         var fmt:TextFormat = new TextFormat();
         fmt.size = size;
         fmt.color = color;
         fmt.align = align;
         fmt.font = "_sans";
         tf.defaultTextFormat = fmt;
         tf.text = "";
         return tf;
      }
      
      private function makeHitZone(name:String, x:int, y:int, w:int, h:int) : Sprite
      {
         var sp:Sprite = new Sprite();
         sp.name = name;
         sp.x = x;
         sp.y = y;
         sp.graphics.beginFill(0,0);
         sp.graphics.drawRect(0,0,w,h);
         sp.graphics.endFill();
         return sp;
      }
      
      private function wrapSkinAsMovieClip(root:Sprite, name:String) : MovieClip
      {
         var obj:DisplayObject = root.getChildByName(name);
         if(obj == null)
         {
            var empty:MovieClip = new MovieClip();
            empty.name = name;
            root.addChild(empty);
            return empty;
         }
         if(obj is MovieClip)
         {
            return obj as MovieClip;
         }
         var wrapper:MovieClip = new MovieClip();
         wrapper.name = name;
         wrapper.x = obj.x;
         wrapper.y = obj.y;
         wrapper.scaleX = obj.scaleX;
         wrapper.scaleY = obj.scaleY;
         wrapper.rotation = obj.rotation;
         obj.x = 0;
         obj.y = 0;
         obj.scaleX = 1;
         obj.scaleY = 1;
         obj.rotation = 0;
         root.removeChild(obj);
         wrapper.addChild(obj);
         root.addChild(wrapper);
         return wrapper;
      }
      
      private function mapExternalChild(root:Sprite, oldName:String, newName:String) : DisplayObject
      {
         var obj:DisplayObject = root.getChildByName(oldName);
         if(obj == null)
         {
            return root.getChildByName(newName);
         }
         var oldTarget:DisplayObject = root.getChildByName(newName);
         if(oldTarget != null && oldTarget != obj)
         {
            root.removeChild(oldTarget);
         }
         obj.name = newName;
         return obj;
      }
      
      private function prepareExternalShopSkin(root:Sprite) : void
      {
         var obj:DisplayObject = null;
         this.mapExternalChild(root,"shopBackground","mainBg");
         this.mapExternalChild(root,"prevButton","prevBt");
         this.mapExternalChild(root,"nextButton","nextBt");
         this.mapExternalChild(root,"backButton","backBt");
         this.mapExternalChild(root,"tab_commend_1","tabBtn100");
         this.mapExternalChild(root,"tab_points_1","tabBtn8");
         this.mapExternalChild(root,"tab_garden_1","tabBtn0");
         this.mapExternalChild(root,"tab_strengthen_1","tabBtn1");
         this.mapExternalChild(root,"tab_house_1","tabBtn7");
         this.mapExternalChild(root,"tab_shop_1","tabBtn5");
         this.mapExternalChild(root,"tab_function_1","tabBtn6");
         this.mapExternalChild(root,"tab_decorate_1","tabBtn3");
         this.mapExternalChild(root,"moneyHeader","moneyBg");
         this.mapExternalChild(root,"gemsHeader","gemsBg");
         var i:int = 1;
         while(i <= this.itemCount)
         {
            this.mapExternalChild(root,"itemSlot" + i,"item" + i);
            i++;
         }
         obj = root.getChildByName("mainBg");
         if(obj != null)
         {
            var bgIndex:int = root.getChildIndex(obj);
            if(bgIndex > 0)
            {
               root.setChildIndex(obj,0);
            }
         }
         this.wrapSkinAsMovieClip(root,"prevBt");
         this.wrapSkinAsMovieClip(root,"nextBt");
         this.wrapSkinAsMovieClip(root,"backBt");
         this.wrapSkinAsMovieClip(root,"tabBtn100");
         this.wrapSkinAsMovieClip(root,"tabBtn8");
         this.wrapSkinAsMovieClip(root,"tabBtn0");
         this.wrapSkinAsMovieClip(root,"tabBtn1");
         this.wrapSkinAsMovieClip(root,"tabBtn7");
         this.wrapSkinAsMovieClip(root,"tabBtn5");
         this.wrapSkinAsMovieClip(root,"tabBtn6");
         this.wrapSkinAsMovieClip(root,"tabBtn3");
         if(root.getChildByName("moneyTxt") == null)
         {
            root.addChild(this.makeTextField("moneyTxt",70,15,90,22,16,16777215,"right"));
         }
         if(root.getChildByName("gemsTxt") == null)
         {
            root.addChild(this.makeTextField("gemsTxt",248,14,105,22,16,16777215,"right"));
         }
         if(root.getChildByName("pointsNumTxt") == null)
         {
            root.addChild(this.makeTextField("pointsNumTxt",375,15,80,22,16,16777215,"left"));
         }
         if(root.getChildByName("pageNumTxt") == null)
         {
            root.addChild(this.makeTextField("pageNumTxt",360,490,80,22,14,16777215,"center"));
         }
         if(root.getChildByName("addGemsBt") == null)
         {
            var ag:MovieClip = new MovieClip();
            ag.name = "addGemsBt";
            root.addChild(ag);
         }
         if(root.getChildByName("addMoneyBt") == null)
         {
            var am:MovieClip = new MovieClip();
            am.name = "addMoneyBt";
            root.addChild(am);
         }
      }
      
      private function prepareExternalItemSlot(root:Sprite, index:int) : Sprite
      {
         var name:String = "item" + index;
         var raw:DisplayObject = root.getChildByName(name);
         if(raw == null)
         {
            return this.buildItemSlot(name,0,0);
         }
         if(raw is Sprite && (raw as Sprite).getChildByName("houseBg") != null)
         {
            return raw as Sprite;
         }
         var px:Number = raw.x;
         var py:Number = raw.y;
         var sx:Number = raw.scaleX;
         var sy:Number = raw.scaleY;
         var rot:Number = raw.rotation;
         root.removeChild(raw);
         var slot:Sprite = this.buildItemSlot(name,0,0);
         var oldBg:DisplayObject = slot.getChildByName("houseBg");
         if(oldBg != null)
         {
            slot.removeChild(oldBg);
         }
         var bg:MovieClip = new MovieClip();
         bg.name = "houseBg";
         raw.x = 0;
         raw.y = 0;
         raw.scaleX = 1;
         raw.scaleY = 1;
         raw.rotation = 0;
         bg.addChild(raw);
         slot.addChildAt(bg,0);
         slot.x = px;
         slot.y = py;
         slot.scaleX = sx;
         slot.scaleY = sy;
         slot.rotation = rot;
         root.addChild(slot);
         return slot;
      }
      
      private function buildShopSkin() : Sprite
      {
         var external:Object = DataManager.getInstance().swfManager.getLoadedSwfContent("itemShop");
         var externalRoot:Sprite = null;
         if(external is Sprite)
         {
            externalRoot = external as Sprite;
         }
         else if(external is DisplayObjectContainer)
         {
            var container:DisplayObjectContainer = external as DisplayObjectContainer;
            externalRoot = new Sprite();
            externalRoot.name = "BG_itemShopUI";
            externalRoot.addChild(container);
         }
         else if(external is DisplayObject)
         {
            var display:DisplayObject = external as DisplayObject;
            externalRoot = new Sprite();
            externalRoot.name = "BG_itemShopUI";
            externalRoot.addChild(display);
         }
         if(externalRoot == null)
         {
            throw new Error("itemShop.swf loaded but returned no DisplayObject content");
         }
         externalRoot.name = "BG_itemShopUI";
         this.prepareExternalShopSkin(externalRoot);
         return externalRoot;
      }
      
      private function buildItemSlot(name:String, x:int, y:int) : Sprite
      {
         var slot:Sprite = new Sprite();
         slot.name = name;
         slot.x = x;
         slot.y = y;
         var houseBg:MovieClip = new MovieClip();
         houseBg.name = "houseBg";
         slot.addChild(houseBg);
         var stateMc:FrameClip = this.makeEmptyFrameClip(11);
         stateMc.name = "stateMc";
         stateMc.x = -6;
         stateMc.y = -6;
         slot.addChild(stateMc);
         var sellOutBg:MovieClip = this.makeHitClip(0,0,115,90);
         sellOutBg.name = "sellOutBg";
         sellOutBg.x = 0;
         sellOutBg.y = 0;
         slot.addChild(sellOutBg);
         var coinIconMc:FrameClip = this.makeEmptyFrameClip(3);
         coinIconMc.name = "coinIconMc";
         coinIconMc.x = 2;
         coinIconMc.y = 96;
         slot.addChild(coinIconMc);
         slot.addChild(this.makeTextField("priceTxt",24,94,60,20,13,0,"left"));
         slot.addChild(this.makeTextField("countNumTxt",95,94,30,20,11,0,"left"));
         var itemDescBg:MovieClip = this.makeHitClip(118,0,125,40);
         itemDescBg.name = "itemDescBg";
         itemDescBg.x = 118;
         itemDescBg.y = 0;
         slot.addChild(itemDescBg);
         slot.addChild(this.makeTextField("itemDescTxt",120,2,125,36,11,16777215,"left"));
         var greenPointMc:MovieClip = this.makeHitClip(118,42,20,20);
         greenPointMc.name = "greenPointMc";
         greenPointMc.x = 118;
         greenPointMc.y = 42;
         slot.addChild(greenPointMc);
         slot.addChild(this.makeTextField("greenPointTxt",142,48,45,20,11,0,"left"));
         slot.addChild(this.makeTextField("discountTxt",118,65,90,16,10,16711680,"left"));
         slot.addChild(this.makeTextField("lockedDesc",8,40,100,30,10,16777215,"center"));
         var unlockBg:MovieClip = this.makeHitClip(0,0,115,90);
         unlockBg.name = "unlockBg";
         unlockBg.x = 0;
         unlockBg.y = 0;
         slot.addChild(unlockBg);
         var unlockCostMc:MovieClip = new MovieClip();
         unlockCostMc.name = "unlockCostMc";
         unlockCostMc.x = 8;
         unlockCostMc.y = 94;
         var unlockCoinIconMc:FrameClip = this.makeEmptyFrameClip(2);
         unlockCoinIconMc.name = "unlockCoinIconMc";
         unlockCostMc["unlockCoinIconMc"] = unlockCoinIconMc;
         unlockCostMc.addChild(unlockCoinIconMc);
         var unlockPriceTxt:TextField = this.makeTextField("unlockPriceTxt",20,0,60,20,12,0,"left");
         unlockCostMc["unlockPriceTxt"] = unlockPriceTxt;
         unlockCostMc.addChild(unlockPriceTxt);
         slot.addChild(unlockCostMc);
         slot.addChild(this.makeTextField("limitTxt",8,40,100,16,10,16777215,"center"));
         slot.addChild(this.makeTextField("limitCDTxt",8,56,100,16,10,16777215,"center"));
         return slot;
      }
      
      private function makeEmptyFrameClip(count:int) : FrameClip
      {
         var clip:FrameClip = new FrameClip();
         var i:int = 0;
         while(i < count)
         {
            clip.addChild(new MovieClip());
            i++;
         }
         return clip;
      }
      
      private function makeHitClip(x:Number, y:Number, w:Number, h:Number) : MovieClip
      {
         var clip:MovieClip = new MovieClip();
         clip.graphics.beginFill(0,0);
         clip.graphics.drawRect(0,0,w,h);
         clip.graphics.endFill();
         clip.x = x;
         clip.y = y;
         return clip;
      }
   }
}

import flash.display.MovieClip;

class FrameClip extends MovieClip
{
   
   public function FrameClip()
   {
      super();
   }
   
   override public function gotoAndStop(frame:Object, scene:String = null) : void
   {
      var total:int = int(this.numChildren);
      if(total == 0)
      {
         return;
      }
      var idx:int = int(frame) - 1;
      if(idx < 0)
      {
         idx = 0;
      }
      if(idx >= total)
      {
         idx = total - 1;
      }
      var i:int = 0;
      while(i < total)
      {
         this.getChildAt(i).visible = i == idx;
         i++;
      }
   }
   
   override public function get totalFrames() : int
   {
      var t:int = int(this.numChildren);
      return t > 0 ? t : 1;
   }
}
