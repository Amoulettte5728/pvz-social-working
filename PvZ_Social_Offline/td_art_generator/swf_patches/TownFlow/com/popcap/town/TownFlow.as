package com.popcap.town
{
   import caurina.transitions.Tweener;
   import com.popcap.framework.components.Alert;
   import com.popcap.framework.components.toolTip.ToolTips;
   import com.popcap.framework.core.Config;
   import com.popcap.framework.core.EnterFrame;
   import com.popcap.framework.core.Lang;
   import com.popcap.framework.events.MyEvent;
   import com.popcap.framework.managers.*;
   import com.popcap.framework.model.FriendVO;
   import com.popcap.framework.net.PVZNetConnection;
   import com.popcap.framework.panel.BagPanel;
   import com.popcap.framework.panel.ItemShopUI;
   import com.popcap.framework.panel.LeaderBoard;
   import com.popcap.framework.panel.questSystem.QuestController;
   import com.popcap.framework.utils.Debug;
   import com.popcap.framework.utils.KeyboardManager;
   import com.popcap.framework.utils.Reflection;
   import com.popcap.framework.utils.StringUtils;
   import com.popcap.pvz.common.policy.CardPolicy;
   import com.popcap.town.build.*;
   import com.popcap.town.data.Data;
   import com.popcap.town.data.GameConfig;
   import com.popcap.town.manager.*;
   import com.popcap.town.panel.*;
   import com.popcap.town.symbol.TownWelcomeInfo;
   import flash.display.Sprite;
   import flash.events.Event;
   import flash.events.EventDispatcher;
   import flash.filters.ColorMatrixFilter;
   import flash.filters.GlowFilter;
   import flash.geom.Point;
   import flash.geom.Rectangle;
   import flash.utils.getTimer;
   import flash.utils.setTimeout;
   
   public class TownFlow
   {
      
      private var bagUI:BagPanel;
      
      private var mainUI:TownUIPanel;
      
      private var missionUI:MissionListPanel;
      
      private var citizenUI:CitizenListPanel;
      
      private var welcomePanel:TownWelcomeInfo;
      
      private var friendBonusPanel:FriendBonusPanel;
      
      private var tutorial:TownTutorialFlow;
      
      private var isFirstLogInTown:Boolean = false;
      
      private var bld:TipsAbleHouse;
      
      private var curCitizenType:int;
      
      private var citizenBldDatIndex:int;
      
      public function TownFlow()
      {
         super();
         this.init();
      }
      
      public function getMainUI() : TownUIPanel
      {
         return this.mainUI;
      }
      
      private function init() : void
      {
         var _loc1_:Boolean = false;
         var _loc2_:Boolean = false;
         this.welcomePanel = new TownWelcomeInfo();
         this.friendBonusPanel = new FriendBonusPanel();
         Data.instance.appFrdArr = FriendManager.instance.getFriendIdList();
         Data.instance.manager.addEventListener(GameConfig.CLICK_FUNCTION_BLD_ITEM,this.onClickFunctionBld);
         Data.instance.manager.addEventListener(GameConfig.CLICK_MODULE_ENTRY_BLD,this.onClickModuleEntryHouse);
         Data.instance.manager.addEventListener(GameConfig.CLICK_FUNCHOUSE_EVENT,this.onClickFuncHouse);
         Data.instance.manager.addEventListener(GameConfig.SELECT_MISSION_MODE,this.onSelMissionMode);
         Data.instance.manager.addEventListener(GameConfig.SELECT_RAMPAGE_MODE,this.onSelRampageMode);
         Data.instance.manager.addEventListener(GameConfig.CLICK_FUNCTION_BLD_CITIZEN_BTN,this.onClickCitizenBldBtn);
         Data.instance.myId = DataManager.getInstance().commonModel.id;
         GameConfig.SELL_BLD_RATE = DataManager.getInstance().pvzData.depreciation;
         DataManager.getInstance().addEventListener(MyEvent.CLICK_FIRNED_ICON,this.onClickFriendItem);
         DataManager.getInstance().addEventListener(MyEvent.TAKING_SEED,this.onTakingSeed);
         DataManager.getInstance().addEventListener(MyEvent.PLANT_SUCCESS,this.onPlantSuccess);
         DataManager.getInstance().addEventListener(MyEvent.BUILD_SUCCESS,this.onBuildSuccess);
         DataManager.getInstance().addEventListener(DEventManager.TAKING_BUILDING,this.onTakingBuilding);
         DataManager.getInstance().addEventListener(MyEvent.SHOW_BAG_ITEM_LIST,this.onClickBagBt);
         if(DataManager.getInstance().cookie.getAttributes("soundSwitch") == null || Boolean(DataManager.getInstance().cookie.getAttributes("soundSwitch")))
         {
            _loc1_ = true;
         }
         else
         {
            _loc1_ = false;
         }
         if(DataManager.getInstance().cookie.getAttributes("musicSwitch") == null || Boolean(DataManager.getInstance().cookie.getAttributes("musicSwitch")))
         {
            _loc2_ = true;
         }
         else
         {
            _loc2_ = false;
         }
         SoundManager.instance.soundSwitch = _loc1_;
         SoundManager.instance.musicSwitch = _loc2_;
         if(this.tutorial == null)
         {
            this.tutorial = new TownTutorialFlow(this);
         }
         this.isFirstLogInTown = true;
         DataManager.getInstance().addEventListener(MyEvent.START_CAPTURE_WAR,this.onStartCapture);
         ActivityManager.instance.reset();
      }
      
      private function __onCloseFriendBonusPanel(param1:MyEvent) : void
      {
      }
      
      public function reset() : void
      {
         var _loc1_:Number = Number(NaN);
         if(Config.OFFLINE_MODE)
         {
         }
         Data.instance.isCompleteTutorial = DataManager.getInstance().commonModel.tutorialStep >= DataManager.TUTORIAL_STEP_COMPLETE;
         if(DataManager.getInstance().isNight)
         {
            Data.instance.iconOverFilter = new GlowFilter(15200604,1,4,4,4,2,false,false);
         }
         else
         {
            Data.instance.iconOverFilter = new GlowFilter(15200604,1,4,4,4,2,false,false);
         }
         Data.instance.iconDisableFilter = new ColorMatrixFilter(GameConfig.garyMatrixArr);
         Data.instance.photoDisableFilter = new ColorMatrixFilter([0.4,0,0,0,38.1,0,0.4,0,0,38.1,0,0,0.4,0,38.1,0,0,0,1,0]);
         DataManager.getInstance().moduleContainer.addChild(Data.instance.mapContainer);
         DataManager.getInstance().ownValudityCardsItemIds = CardPolicy.getValidityItemIds(DataManager.getInstance().ownCardsData);
         DataManager.getInstance().ownValudityCardsPlantIds = CardPolicy.getValudityPlantIds(DataManager.getInstance().ownValudityCardsItemIds);
         if(Data.instance.skyMc == null)
         {
            Data.instance.skyMc = new Sprite();
            Data.instance.skyMc.mouseEnabled = false;
         }
         DataManager.getInstance().moduleContainer.addChild(Data.instance.skyMc);
         if(Data.instance.aniManager == null)
         {
            Data.instance.aniManager = new TownAnimationManager();
         }
         this.loadHouseSetting();
         this.loadUserTownInfo();
         if(Config.OFFLINE_MODE)
         {
            KeyboardManager.registerKey("F5",this.onSwitchTdMode);
         }
         Data.instance.setProperty("tdModeName","newTD");
         if(DataManager.getInstance().startLoadingTime > 0)
         {
            _loc1_ = getTimer() - DataManager.getInstance().startLoadingTime;
            PVZNetConnection.getInstance().sendAndCall("services.I1029",null,_loc1_);
            DataManager.getInstance().startLoadingTime = 0;
         }
      }
      
      private function loadHouseSetting() : void
      {
         if(DataManager.getInstance().houseMissionMap == null)
         {
            PVZNetConnection.getInstance().sendAndCall("services.I1033",this.onGetHouseMissionSetting);
         }
      }
      
      private function onGetHouseMissionSetting(param1:Object) : void
      {
         var _loc3_:String = null;
         var _loc4_:Array = null;
         var _loc2_:Object = param1.list;
         DataManager.getInstance().houseMissionMap = {};
         for(_loc3_ in _loc2_)
         {
            _loc4_ = _loc2_[_loc3_] as Array;
            DataManager.getInstance().houseMissionMap[int(_loc3_)] = _loc4_;
         }
         if(this.mainUI != null)
         {
            this.resetRampageBt();
         }
      }
      
      private function onSwitchTdMode() : void
      {
         PropItemsManager.instace.adjPropNum(706,1);
      }
      
      private function onClickFunctionBld(param1:MyEvent) : void
      {
         var _loc2_:EventDispatcher = null;
         var _loc3_:String = null;
         var _loc4_:Sprite = null;
         var _loc5_:Rectangle = null;
         this.bld = param1.data.bld as TipsAbleHouse;
         if(this.bld == null)
         {
            return;
         }
         if(this.bld.subType == GameConfig.BLD_TYPE_BIZ)
         {
            if(Data.instance.isMySelf)
            {
               if(this.bld.bldTipsState == GameConfig.BLD_STATE_READY)
               {
                  this.requestIncome(param1);
               }
               else
               {
                  SoundManager.instance.createSound(SoundManager.PAPER,DataManager.getInstance().soundApp);
                  this.showCitizenList(this.bld.subType,this.bld.dataIndex);
               }
            }
         }
         else if(this.bld.subType == GameConfig.BLD_TYPE_HOMES)
         {
            this.openAdventureForHouse(this.bld);
            return;
         }
      }
      
      private function onRentalError(param1:MyEvent) : void
      {
         DataManager.getInstance().waiting.hideMask();
         param1.currentTarget.removeEventListener(MyEvent.FAILD,this.onRentalError);
      }
      
      private function onRentalComplete(param1:Object) : void
      {
         var _loc2_:Point = this.bld.parent.localToGlobal(new Point(this.bld.x + int(this.bld.width * 0.25),this.bld.y + 10));
         IconMovieManager.instance.showEnergyMovie(-DataManager.ENERGY_IN_ROOM,[_loc2_.x,_loc2_.y]);
         DataManager.getInstance().questCheckSWFDO.dispatchEvent(new MyEvent(QuestController.LIVE_IN_HOUSE,Data.instance.townOwnerId));
         Data.instance.setProperty("selRentalBuildingResult",param1);
         var _loc3_:TipsAbleHouse = Data.instance.getProperty("selRentalBuilding") as TipsAbleHouse;
         _loc3_.addEventListener(GameConfig.SUN_FLOW_ANI_PLAY_COMPLETE,this.onRentalMoviePlayComplete);
         _loc3_.dispatchEvent(new MyEvent(MyEvent.SUN_FLOWER_PROGRESS));
      }
      
      private function onRentalMoviePlayComplete(param1:MyEvent) : void
      {
         var _loc5_:Object = null;
         var _loc6_:Array = null;
         var _loc7_:* = 0;
         var _loc8_:Object = null;
         var _loc9_:Building = null;
         DataManager.getInstance().waiting.hideMask();
         var _loc2_:TipsAbleHouse = Data.instance.getProperty("selRentalBuilding") as TipsAbleHouse;
         _loc2_.removeEventListener(GameConfig.SUN_FLOW_ANI_PLAY_COMPLETE,this.onRentalMoviePlayComplete);
         Data.instance.setProperty("selRentalBuilding",null);
         var _loc3_:Object = Data.instance.getProperty("selRentalBuildingResult");
         Data.instance.setProperty("selRentalBuildingResult",null);
         if(_loc3_ != null && Boolean(_loc3_.result) && _loc2_ != null)
         {
            _loc5_ = Data.instance.allItemArr[_loc2_.dataIndex];
            if(_loc5_ != null && _loc3_.building != null)
            {
               _loc5_.occupier = "" + Data.instance.myId;
               _loc5_.leaveTime = _loc3_.building.leaveTime;
               _loc2_.setData(_loc5_);
               Data.instance.isInThisCity = true;
               _loc6_ = Data.instance.cityDataObj.buildings as Array;
               _loc7_ = _loc6_.length - 1;
               while(_loc7_ >= 0)
               {
                  _loc8_ = _loc6_[_loc7_];
                  _loc9_ = Data.instance.manager.getBuildingAtPosition(_loc8_.position);
                  if(_loc9_ is PeopleHouse)
                  {
                     _loc9_.setData(_loc8_);
                  }
                  _loc7_--;
               }
               CitizenListPanel.isRoomerRequest = false;
            }
         }
         var _loc4_:Sprite = Reflection.createSprite("inviteFrdSuccessMc",Data.instance.app);
         _loc4_.x = (GameConfig.TOWN_WIDTH - _loc4_.width) * 0.5;
         _loc4_.y = (GameConfig.TOWN_HEIGHT - _loc4_.height) * 0.5;
         _loc4_.alpha = 0;
         Tweener.addTween(_loc4_,{
            "alpha":1,
            "time":2
         });
         Data.instance.uiMc.addChild(_loc4_);
         setTimeout(this.hideRentalMovie,3000,_loc4_);
      }
      
      private function hideRentalMovie(param1:Sprite) : void
      {
         Tweener.addTween(param1,{
            "alpha":0,
            "time":2,
            "onComplete":Data.instance.uiMc.removeChild,
            "onCompleteParams":[param1]
         });
      }
      
      private function onSelMissionMode(param1:MyEvent) : void
      {
         var _loc2_:Building = null;
         if(param1 != null)
         {
            _loc2_ = param1.data.bld as Building;
         }
         if(_loc2_ == null)
         {
            _loc2_ = Data.instance.getProperty("selBld") as Building;
         }
         if(_loc2_ == null)
         {
            Debug.trace("无法找到开始td的房屋");
            return;
         }
         trace("[DEBUG-HOUSECLICK] onSelMissionMode: tid=" + _loc2_.tid + " subType=" + _loc2_.subType + " -> opening adventure panel");
         this.openAdventureForHouse(_loc2_);
      }
      
      public function getRamPageHousePos() : int
      {
         var _loc1_:int = 0;
         var _loc4_:Building = null;
         var _loc5_:int = 0;
         var _loc6_:Array = null;
         var _loc2_:Array = Data.instance.manager.getAllItemArr();
         var _loc3_:* = _loc2_.length - 1;
         while(_loc3_ >= 0)
         {
            _loc4_ = _loc2_[_loc3_] as Building;
            if(_loc4_ != null && _loc4_ is PeopleHouse)
            {
               _loc5_ = _loc4_.tid;
               _loc6_ = DataManager.getInstance().houseMissionMap[_loc5_];
               if(_loc6_ != null && _loc6_.length > 0 && _loc6_[0] <= 0)
               {
                  _loc1_ = _loc4_.getPos();
                  break;
               }
            }
            _loc3_--;
         }
         return _loc1_;
      }
      
      private function resetRampageBt() : void
      {
         var _loc3_:Sprite = null;
         var _loc1_:int = this.getRamPageHousePos();
         var _loc2_:Sprite = this.mainUI.getSkin().getChildByName("btListMc") as Sprite;
         _loc3_ = _loc2_.getChildByName("rpBt") as Sprite;
         if(_loc1_ <= 0 && Data.instance.isMySelf)
         {
            _loc2_.x = 201;
            _loc3_.visible = false;
         }
         else
         {
            _loc2_.x = 271;
            if(Data.instance.isMySelf)
            {
               _loc3_.visible = true;
            }
            else
            {
               _loc3_.visible = false;
            }
         }
      }
      
      private function onBuildSuccess(param1:MyEvent) : void
      {
         this.resetRampageBt();
      }
      
      private function onSelRampageMode(param1:MyEvent) : void
      {
         var _loc2_:int = this.getRamPageHousePos();
         if(_loc2_ <= 0)
         {
            return;
         }
         this.onClickRamPageBt(_loc2_);
      }
      
      private function onClickModuleEntryHouse(param1:MyEvent) : void
      {
         var _loc2_:FunctionEntryHouse = param1.data.bld as FunctionEntryHouse;
         if(_loc2_ != null)
         {
            if(_loc2_.MODULE_INDEX == 1)
            {
            }
         }
      }
      
      private function onClickFuncHouse(param1:MyEvent) : void
      {
         var _loc2_:Building = param1.data.bld as Building;
         if(_loc2_ == null)
         {
            return;
         }
         this.openAdventureForHouse(_loc2_);
      }
      
      private function openAdventureForHouse(param1:Building) : void
      {
         var missions:Array = null;
         var mapped:Array = null;
         var i:int = 0;
         if(param1 == null)
         {
            return;
         }
         if(!Data.instance.isMySelf)
         {
            Alert.instance.show(Data.instance.uiMc,Lang.getLocalizationString(Lang.POPUP,Lang.MISSION_CENTER,"FRIEND_TOWN_NO_ADVENTURE"),null,null,null,true,false);
            return;
         }
         Data.instance.setProperty("selBld",param1);
         if(DataManager.getInstance().houseMissionMap != null)
         {
            mapped = DataManager.getInstance().houseMissionMap[param1.tid] as Array;
         }
         missions = [];
         if(mapped != null)
         {
            i = 0;
            while(i < mapped.length)
            {
               if(int(mapped[i]) > 0)
               {
                  missions.push(mapped[i]);
               }
               i++;
            }
         }
         if(missions.length <= 0)
         {
            missions = [1];
         }
         trace("[DEBUG-HOUSECLICK] openAdventureForHouse: tid=" + param1.tid + " missions=" + missions.join(","));
         this.showMissionList(param1,missions);
      }
      
      private function requestIncome(param1:MyEvent, param2:Boolean = true) : void
      {
         var _loc3_:Building = null;
         var _loc4_:Point = null;
         var _loc5_:String = null;
         var _loc6_:Sprite = null;
         var _loc7_:Rectangle = null;
         if(param1.data != null)
         {
            if(EnergyManager.instance.isEnoughEnergy(DataManager.ENERGY_SHOP_PAYOFF_VALUE) == false)
            {
               _loc5_ = Lang.getLocalizationString(Lang.UI,"ENERGY","ENERGY_PAYOFF_NOT_ENOUGH");
               Alert.instance.show(DataManager.getInstance().uiContainer,_loc5_,[380,300],null,null,true,false);
               return;
            }
            PVZNetConnection.getInstance().sendQueueToServer();
            _loc3_ = param1.data.bld;
            PVZNetConnection.getInstance().sendAndCall("services.I2020",null,_loc3_.buyId);
            Data.instance.setProperty("bld",_loc3_);
            if(param2)
            {
               _loc3_.dispatchEvent(new MyEvent(MyEvent.SUN_FLOWER_PROGRESS,this.incomeProgComplete));
            }
            else
            {
               this.onGetPrizeResult(_loc3_,false);
            }
            DataManager.getInstance().questCheckSWFDO.dispatchEvent(new MyEvent(QuestController.GET_COIN_FROM_BUILDING,_loc3_.tid));
            _loc4_ = _loc3_.parent.localToGlobal(new Point(_loc3_.x + int(_loc3_.width * 0.25),_loc3_.y + 10));
            IconMovieManager.instance.showEnergyMovie(-DataManager.ENERGY_SHOP_PAYOFF_VALUE,[_loc4_.x,_loc4_.y]);
            if((DataManager.getInstance().commonModel.tutorialStep & DataManager.TUTORIAL_STEP_BIZ_HOUSE_INCOME) <= 0)
            {
               PVZNetConnection.getInstance().sendAndCall("services.I1019",null,DataManager.TUTORIAL_STEP_BIZ_HOUSE_INCOME);
               RemindManager.instance.hideHightLightArea();
               RemindManager.instance.hideLabelRemind();
               _loc6_ = Data.instance.uiMc.getChildByName("mainUIMc") as Sprite;
               if(_loc6_ == null)
               {
                  return;
               }
               _loc6_ = _loc6_.getChildByName("energyMc") as Sprite;
               if(_loc6_ == null)
               {
                  return;
               }
               _loc7_ = _loc6_.getRect(Data.instance.uiMc);
               RemindManager.instance.showHightLightArea(_loc7_,true,true);
               RemindManager.instance.showLabelRemind(Lang.getLocalizationString(Lang.REMINDING,Lang.TUTORIAL,"FIRST_HARVEST_BIZ_HOUSE"),-1,false,2);
            }
         }
      }
      
      private function onClickCitizenBldBtn(param1:MyEvent) : void
      {
         this.requestIncome(param1,false);
      }
      
      private function incomeProgComplete(param1:Building) : void
      {
         this.onGetPrizeResult(param1);
      }
      
      private function onGetPrizeResult(param1:Building = null, param2:Boolean = true) : void
      {
         if(param1 == null)
         {
            return;
         }
         SoundManager.instance.createSound(SoundManager.POINTS,DataManager.getInstance().soundApp);
         var _loc3_:Object = Data.instance.itemConfArr[param1.id];
         var _loc4_:Object = Data.instance.allItemArr[param1.dataIndex];
         Data.instance.setProperty("bld",null);
         if(_loc4_ != null)
         {
            _loc4_.coolDown = Data.instance.time.millisecondToCDUTCTime(Data.instance.time.serverTime + Number(_loc3_.coolDown) * 1000);
            param1.setData(_loc4_);
         }
         if(this.citizenUI != null && Data.instance.uiMc.contains(this.citizenUI.getSkin()))
         {
            this.citizenUI.reset(this.citizenUI.itemType);
         }
         var _loc5_:Array = [];
         _loc5_[0] = param1.x + param1.width * 0.5;
         _loc5_[1] = param1.y;
         if(param2)
         {
            Data.instance.aniManager.createNewMoneyDropItem(_loc5_[0],_loc5_[1],_loc3_.income);
            if(int(_loc3_.exp) > 0)
            {
               Data.instance.aniManager.createNewExpDropItem(_loc5_[0],_loc5_[1],int(_loc3_.exp));
            }
         }
      }
      
      private function showCitizenList(param1:int = 0, param2:int = -1) : void
      {
         EnterFrame.pause = true;
         this.curCitizenType = param1;
         this.citizenBldDatIndex = param2;
         if(Data.instance.housesEnegryList == null)
         {
            DataManager.getInstance().waiting.show("");
            PVZNetConnection.getInstance().sendAndCall("services.I1034",this.onGetHouseEnegrySetting);
         }
         else
         {
            this.onGetCitizenData();
         }
      }
      
      private function onGetHouseEnegrySetting(param1:Object) : void
      {
         DataManager.getInstance().waiting.hide();
         Data.instance.housesEnegryList = param1.energyLimit[2];
         trace("[DEBUG-CITIZEN] onGetHouseEnegrySetting: got response, calling onGetCitizenData()");
         this.onGetCitizenData();
      }
      
      private function onGetCitizenData() : void
      {
         trace("[DEBUG-CITIZEN] onGetCitizenData: opening UI_RESOURCE_BUILDING_LIST panel");
         UIResourceManager.instance.openPanel(UIResourceManager.UI_RESOURCE_BUILDING_LIST,this.onGetCitizenUIResource,[this.curCitizenType,this.citizenBldDatIndex],Data.instance.app);
      }
      
      private function onGetCitizenUIResource(param1:int, param2:int = -1) : void
      {
         trace("[DEBUG-CITIZEN] onGetCitizenUIResource: reached, citizenUI==null? " + (this.citizenUI == null));
         if(this.citizenUI == null)
         {
            this.citizenUI = new CitizenListPanel();
            this.citizenUI.setSkin(Reflection.createSprite("citizenListMc",Data.instance.app));
            this.citizenUI.addEventListener(MyEvent.CLOSE,this.onCloseCitizenList);
            this.citizenUI.addEventListener("gotoBuildShop",this.citizenToBldShop);
            this.citizenUI.addEventListener("getIncome",this.requestIncome);
            this.citizenUI.addEventListener("gotoItemShop",this.onClickItemShopBt);
         }
         trace("[DEBUG-CITIZEN] onGetCitizenUIResource: citizenUI.getSkin()==null? " + (this.citizenUI.getSkin() == null));
         this.lockScreen(true);
         var _loc3_:Sprite = this.citizenUI.getSkin();
         if(!Data.instance.uiMc.contains(_loc3_))
         {
            Data.instance.uiMc.addChild(_loc3_);
         }
         _loc3_.x = (GameConfig.TOWN_WIDTH - _loc3_.width) * 0.5;
         _loc3_.y = 40;
         this.citizenUI.reset(param1,param2);
      }
      
      private function citizenToBldShop(param1:MyEvent) : void
      {
         this.onCloseCitizenList(null);
         var _loc2_:int = int(param1.data);
         if(_loc2_ == 1)
         {
            _loc2_ = ItemShopUI.CATEGORY_HOUSE;
         }
         else if(_loc2_ == 2)
         {
            _loc2_ = ItemShopUI.CATEGORY_SHOP;
         }
         PVZNetConnection.getInstance().sendQueueToServer();
         var _loc3_:ItemShopUI = DataManager.getInstance().itemShowUI;
         if(_loc3_ != null)
         {
            DataManager.getInstance().itemShowUI.showItemShopUI(-1,_loc2_);
         }
      }
      
      private function onCloseCitizenList(param1:MyEvent) : void
      {
         this.lockScreen(false);
         EnterFrame.pause = false;
         if(Data.instance.uiMc.contains(this.citizenUI.getSkin()))
         {
            Data.instance.uiMc.removeChild(this.citizenUI.getSkin());
         }
      }
      
      private function moveBuilding(param1:MyEvent) : void
      {
         Data.instance.actionMode = GameConfig.MOVE_MODE;
         Data.instance.isEditMode = true;
         Data.instance.manager.moveBuilding(param1.data.bld);
      }
      
      private function showTownMovie() : void
      {
         DataManager.getInstance().swfManager.setLoadingVisible(false);
         DataManager.getInstance().addEventListener(MyEvent.FINISHED_SCENE_CHANGE,this.onShowEnterMoveComplete);
         Data.instance.doc.dispatchEvent(new MyEvent(MyEvent.ENTRY_MODULE_COMPLETE));
         if(DataManager.getInstance().commonModel.tutorialStep != 0)
         {
            DataManager.getInstance().dispatchEvent(new Event(DataManager.EVENT_TYPE_CHANGESCENE));
         }
      }
      
      private function onShowEnterMoveComplete(param1:MyEvent) : void
      {
         DataManager.getInstance().removeEventListener(MyEvent.FINISHED_SCENE_CHANGE,this.onShowEnterMoveComplete);
         Data.instance.aniManager.showCloud(3);
         if(DataManager.getInstance().commonModel.tutorialStep == DataManager.TUTORIAL_STEP_START)
         {
            this.tutorial.completeTutorialWelcomeMovie();
         }
         else if(Data.instance.isCompleteTutorial)
         {
            this.tutorial.checkOtherTutorial();
         }
      }
      
      private function loadUserTownInfo() : void
      {
         Data.instance.aniManager.showTownOutsideZombie(0,true);
         Data.instance.aniManager.showTownInsideZombie(0,true);
         Data.instance.aniManager.clearAllItems(true);
         Data.instance.isMySelf = Data.instance.townOwnerId == DataManager.getInstance().commonModel.id;
         PVZNetConnection.getInstance().sendAndCall("services.I2001",this.onGetUserTownInfo,"" + Data.instance.townOwnerId);
      }
      
      private function showMissionList(param1:Building, param2:Array) : void
      {
         UIResourceManager.instance.openPanel(UIResourceManager.UI_RESOURCE_ADVENTURE,this.onGetMissionUIResource,[param1,param2],Data.instance.app);
      }
      
      private function onGetMissionUIResource(param1:Building, param2:Array) : void
      {
         if(this.missionUI == null)
         {
            this.missionUI = new MissionListPanel();
            this.missionUI.setSkin(Reflection.createSprite("missionList",Data.instance.app));
            this.missionUI.addEventListener("closeMissionUI",this.onCloseMissionUI);
         }
         EnterFrame.pause = true;
         this.missionUI.reset(param1,param2);
         this.lockScreen(true);
         Data.instance.setProperty("missionBldDatIndex",param1 == null ? 0 : param1.dataIndex);
      }
      
      private function onClickFriendItem(param1:MyEvent) : void
      {
         var _loc2_:int = int(param1.data);
         if(Data.instance.townOwnerId == _loc2_)
         {
            return;
         }
         Data.instance.townOwnerId = _loc2_;
         var _loc3_:String = FriendManager.instance.getFriendVO(_loc2_).name;
         DataManager.getInstance().waiting.show(Lang.getLocalizationString(Lang.UI,Lang.TOWN,"GOTO_FRIEND_TOWN",_loc3_));
         PVZNetConnection.getInstance().sendQueueToServer();
         DataManager.getInstance().changeScenePanel.setOldModule(DataManager.getInstance().moduleContainer);
         this.loadUserTownInfo();
      }
      
      private function onClickCitizenListBt(param1:MyEvent) : void
      {
         this.showCitizenList();
      }
      
      private function onClickCardBt(param1:MyEvent) : void
      {
         var _loc2_:int = int(Data.instance.cityDataObj.city.uid);
         DataManager.getInstance().dispatchEvent(new MyEvent(MyEvent.SHOW_FRIEND_LIST,false));
         Data.instance.doc.dispatchEvent(new MyEvent(MyEvent.EXIT_MODULE,{
            "newModule":"garden",
            "args":["cardCompose",_loc2_]
         }));
      }
      
      private function onClickItemShopBt(param1:MyEvent) : void
      {
         EnterFrame.pause = true;
         UIResourceManager.instance.openPanel(UIResourceManager.UI_RESOURCE_ITEM_SHOP,this.openItemShop,[param1]);
      }
      
      private function openItemShop(param1:MyEvent) : void
      {
         this.lockScreen(true);
         PVZNetConnection.getInstance().sendQueueToServer();
         DataManager.getInstance().addEventListener(MyEvent.REMOVE_ITEM_SHOP,this.removeItemShop);
         DataManager.getInstance().dispatchEvent(new MyEvent(MyEvent.SHOW_ITEM_SHOP_UI,param1.data));
      }
      
      private function removeItemShop(param1:MyEvent) : void
      {
         DataManager.getInstance().removeEventListener(MyEvent.REMOVE_ITEM_SHOP,this.removeItemShop);
         EnterFrame.pause = false;
         this.lockScreen(false);
         if(this.citizenUI != null && Data.instance.uiMc.contains(this.citizenUI.getSkin()))
         {
            this.citizenUI.reset();
         }
      }
      
      private function onClickBagBt(param1:MyEvent) : void
      {
         UIResourceManager.instance.openPanel(UIResourceManager.UI_RESOURCE_BAG_PANEL,this.showBagList,null,Data.instance.app);
      }
      
      private function showBagList(param1:int = -1) : void
      {
         EnterFrame.pause = true;
         if(this.bagUI == null)
         {
            this.bagUI = new BagPanel();
            this.bagUI.addEventListener(MyEvent.CLOSE,this.onCloseBagUI);
            this.bagUI.setSkin(Reflection.createSprite("bagUIMc",Data.instance.app));
         }
         this.bagUI.reset(param1);
         DataManager.getInstance().waiting.showMask(Data.instance.uiMc);
         Data.instance.uiMc.addChild(this.bagUI.getSkin());
      }
      
      private function onCloseBagUI(param1:MyEvent) : void
      {
         EnterFrame.pause = false;
         Data.instance.uiMc.removeChild(this.bagUI.getSkin());
         DataManager.getInstance().waiting.hideMask();
      }
      
      private function onClickRamPageBt(param1:int) : void
      {
         UIResourceManager.instance.openPanel(UIResourceManager.UI_RESOURCE_RAMPAGE_PANEL,this.openRampageEntryPanel,[param1]);
      }
      
      private function openRampageEntryPanel(param1:int) : void
      {
         var _loc2_:String = null;
         if((DataManager.getInstance().commonModel.tutorialStep & DataManager.TUTORIAL_STEP_RAMPAGE) <= 0)
         {
            RemindManager.instance.hideHightLightArea();
            RemindManager.instance.hideLabelRemind();
            DataManager.getInstance().dispatchEvent(new MyEvent(MyEvent.SHOW_FRIEND_LIST,false));
            Data.instance.setProperty("lastGameModule","rampage");
            Data.instance.doc.dispatchEvent(new MyEvent(MyEvent.EXIT_MODULE,{
               "newModule":"newTD",
               "args":[{"type":103}]
            }));
            return;
         }
         if(DataManager.getInstance().commonModel.level < DataManager.getInstance().rampageLevelRequired)
         {
            _loc2_ = Lang.getLocalizationString(Lang.POPUP,Lang.TOWN,"RAMPAGE_LEVEL_REQUIRED");
            Alert.instance.show(Data.instance.uiMc,StringUtils.replace(_loc2_,"####","" + DataManager.getInstance().rampageLevelRequired),null,null,null,true,false);
            return;
         }
         if(DataManager.getInstance().leaderBoard == null)
         {
            DataManager.getInstance().leaderBoard = new LeaderBoard();
            DataManager.getInstance().leaderBoard.enterContainer();
         }
         if(!DataManager.getInstance().rampageEntryPannel.hasEventListener("start_ram_page"))
         {
            DataManager.getInstance().rampageEntryPannel.addEventListener("start_ram_page",this.onStartRamPage);
         }
         Data.instance.uiMc.addChild(DataManager.getInstance().leaderBoard);
         DataManager.getInstance().leaderBoard.y = 25;
         DataManager.getInstance().rampageEntryPannel.show(Data.instance.uiMc);
         DataManager.getInstance().rampageEntryPannel.hc.enterContainer();
         DataManager.getInstance().rampageEntryPannel.pos = param1;
         DataManager.getInstance().rampageEntryPannel.skin.y = 25;
      }
      
      private function onStartRamPage(param1:MyEvent) : void
      {
         var _loc2_:Object = {"setting":{"type":102}};
         DataManager.getInstance().dispatchEvent(new MyEvent(MyEvent.SHOW_FRIEND_LIST,false));
         Data.instance.tdHouseId = param1.data.tdHouseId;
         Data.instance.tdSoldierId = param1.data.tdSoldierId;
         Data.instance.tdBuildId = param1.data.tdBuildingId;
         if(Data.instance.getProperty("tdModeName") == "newTD")
         {
            Data.instance.doc.dispatchEvent(new MyEvent(MyEvent.EXIT_MODULE,{
               "newModule":"newTD",
               "args":[_loc2_.setting,param1.data]
            }));
         }
         else
         {
            Data.instance.doc.dispatchEvent(new MyEvent(MyEvent.EXIT_MODULE,{
               "newModule":"td",
               "args":[_loc2_,param1.data]
            }));
         }
         DataManager.getInstance().leaderBoard.removeFromContainer();
      }
      
      private function onStartCapture(param1:MyEvent) : void
      {
         var _loc2_:Object = {"setting":{"type":104}};
         Data.instance.doc.dispatchEvent(new MyEvent(MyEvent.EXIT_MODULE,{
            "newModule":"newTD",
            "args":[_loc2_.setting,null,param1.data]
         }));
      }
      
      private function onCloseMissionUI(param1:MyEvent) : void
      {
         var _loc2_:Object = null;
         var _loc3_:Object = null;
         EnterFrame.pause = false;
         if(param1.data != null)
         {
            _loc2_ = {};
            _loc3_ = Data.instance.getProperty("missionXml");
            DataManager.getInstance().dispatchEvent(new MyEvent(MyEvent.SHOW_FRIEND_LIST,false));
            _loc2_.tdSoldierId = Data.instance.tdSoldierId;
            _loc2_.tdHouseId = Data.instance.tdHouseId;
            _loc2_.tdBuildingId = Data.instance.tdBuildId;
            ToolTips.instance.hideToolTips();
            if(Data.instance.getProperty("tdModeName") == "newTD")
            {
               Data.instance.doc.dispatchEvent(new MyEvent(MyEvent.EXIT_MODULE,{
                  "newModule":"newTD",
                  "args":[_loc3_.setting,_loc2_]
               }));
            }
            else
            {
               Data.instance.doc.dispatchEvent(new MyEvent(MyEvent.EXIT_MODULE,{
                  "newModule":"td",
                  "args":[_loc3_,_loc2_]
               }));
            }
            Data.instance.setProperty("missionXml",null);
         }
         else
         {
            Data.instance.uiMc.removeChild(this.missionUI.getSkin());
            this.lockScreen(false);
         }
      }
      
      public function dispose() : void
      {
         Data.instance.aniManager.clearAllItems(false);
         ToolTips.instance.hideToolTips();
         Data.instance.manager.removeEventListener(GameConfig.CLICK_FUNCTION_BLD_ITEM,this.onClickFunctionBld);
         Data.instance.manager.removeEventListener(GameConfig.CLICK_MODULE_ENTRY_BLD,this.onClickModuleEntryHouse);
         Data.instance.manager.removeEventListener(GameConfig.SELECT_MISSION_MODE,this.onSelMissionMode);
         Data.instance.manager.removeEventListener(GameConfig.SELECT_RAMPAGE_MODE,this.onSelRampageMode);
         Data.instance.manager.removeEventListener(GameConfig.CLICK_FUNCHOUSE_EVENT,this.onClickFuncHouse);
         DataManager.getInstance().removeEventListener(MyEvent.TAKING_SEED,this.onTakingSeed);
         DataManager.getInstance().rampageEntryPannel.removeEventListener("start_ram_page",this.onStartRamPage);
         DataManager.getInstance().removeEventListener(MyEvent.PLANT_SUCCESS,this.onPlantSuccess);
         DataManager.getInstance().removeEventListener(DEventManager.TAKING_BUILDING,this.onTakingBuilding);
         DataManager.getInstance().removeEventListener(MyEvent.CLICK_FIRNED_ICON,this.onClickFriendItem);
         DataManager.getInstance().removeEventListener(MyEvent.BUILD_SUCCESS,this.onBuildSuccess);
         DataManager.getInstance().removeEventListener(MyEvent.SHOW_BAG_ITEM_LIST,this.onClickBagBt);
         this.lockScreen(false);
         Data.instance.aniManager.dispose();
         Data.instance.aniManager = null;
         DataManager.getInstance().removeEventListener(MyEvent.FINISHED_SCENE_CHANGE,this.onShowEnterMoveComplete);
         DataManager.getInstance().moduleContainer.removeChild(Data.instance.skyMc);
         DataManager.getInstance().moduleContainer.removeChild(Data.instance.mapContainer);
         if(this.mainUI != null)
         {
            this.mainUI.removeEventListener("showCitizenList",this.onClickCitizenListBt);
            this.mainUI.removeEventListener("showCardModule",this.onClickCardBt);
            this.mainUI.removeEventListener(MyEvent.SHOW_BAG_ITEM_LIST,this.onClickBagBt);
            this.mainUI.dispose();
            this.mainUI = null;
         }
         if(this.missionUI != null)
         {
            if(Data.instance.uiMc.contains(this.missionUI.getSkin()))
            {
               Data.instance.uiMc.removeChild(this.missionUI.getSkin());
            }
            this.missionUI.removeEventListener("closeMissionUI",this.onCloseMissionUI);
            this.missionUI.dispose();
            this.missionUI = null;
         }
         if(this.citizenUI != null)
         {
            this.citizenUI.removeEventListener(MyEvent.CLOSE,this.onCloseCitizenList);
            this.citizenUI.removeEventListener("gotoBuildShop",this.citizenToBldShop);
            this.citizenUI.removeEventListener("getIncome",this.requestIncome);
            this.citizenUI.dispose();
            this.citizenUI = null;
         }
      }
      
      public function lockScreen(param1:Boolean = true, param2:Boolean = true) : void
      {
         Data.instance.mapContainer.mouseEnabled = Data.instance.mapContainer.mouseChildren = !param1;
         if(this.mainUI != null && this.mainUI.getSkin() != null)
         {
            this.mainUI.getSkin().mouseChildren = !param1;
         }
         if(param2)
         {
            DataManager.getInstance().frdListUI.mouseEnabled = DataManager.getInstance().frdListUI.mouseChildren = !param1;
         }
      }
      
      private function onTakingBuilding(param1:MyEvent) : void
      {
         var _loc2_:int = int(param1.data.id);
         trace("[DEBUG-SHOP] TownFlow.onTakingBuilding: id=" + _loc2_ + " calling Manager.addAndDrapNewItem()");
         if(param1.data.isBuy == false)
         {
            Data.instance.actionMode = GameConfig.PUT_MODE;
            Data.instance.isEditMode = true;
         }
         Data.instance.manager.addAndDrapNewItem(_loc2_);
         if(DataManager.getInstance().commonModel.tutorialStep == DataManager.TUTORIAL_STEP_BUY_HOUSE)
         {
            this.tutorial.showTutorialBuyHouse3();
         }
      }
      
      private function onTakingSeed(param1:MyEvent) : void
      {
         var _loc2_:String = null;
         var _loc3_:Object = null;
         if(param1.data == null)
         {
            Data.instance.isPlanting = false;
            Data.instance.isNewBuilding = false;
            Data.instance.isEditMode = false;
         }
         else
         {
            _loc2_ = String(param1.data);
            _loc3_ = DataManager.getInstance().propItemsConfigMap.get(_loc2_);
            Data.instance.manager.addAndDrapNewItem(_loc3_.resourceId);
         }
      }
      
      private function onPlantSuccess(param1:MyEvent) : void
      {
         SoundManager.instance.createSound(SoundManager.PLANT2,DataManager.getInstance().soundApp,100,int.MAX_VALUE);
      }
      
      private function onGetUserTownInfo(param1:Object) : void
      {
         var _loc10_:* = 0;
         var _loc11_:Object = null;
         var _loc12_:FriendVO = null;
         var _loc13_:String = null;
         var _loc14_:String = null;
         var _loc15_:Array = null;
         DataManager.getInstance().waiting.hide();
         if(param1 == null)
         {
            Debug.trace("block:获取数据时出错!");
            Alert.instance.show(Data.instance.uiMc,Lang.getLocalizationString(Lang.POPUP,Lang.TOWN,"GET_CITY_INFO_ERROR"));
            return;
         }
         Data.instance.isInThisCity = false;
         if(!Data.instance.isMySelf)
         {
            DataManager.getInstance().questCheckSWFDO.dispatchEvent(new MyEvent(QuestController.VISIT_FRIEND_TOWN,Data.instance.townOwnerId));
            if(param1.buildings == null || param1.buildings.length <= 0)
            {
               Data.instance.isInThisCity = false;
            }
            else
            {
               _loc10_ = int(param1.buildings.length - 1);
               while(_loc10_ >= 0)
               {
                  _loc11_ = param1.buildings[_loc10_];
                  if(_loc11_ != null && _loc11_.occupier != null && _loc11_.occupier != "" && Number(_loc11_.occupier) == Data.instance.myId)
                  {
                     if(Data.instance.time.UTCTimerTOMillisecond(_loc11_.leaveTime) > Data.instance.time.serverTime)
                     {
                        Data.instance.isInThisCity = true;
                        break;
                     }
                  }
                  _loc10_--;
               }
            }
         }
         var _loc2_:Boolean = Data.instance.cityDataObj == null;
         Data.instance.isAutoSave = true;
         Data.instance.cityDataObj = param1;
         if(Data.instance.isMySelf)
         {
            DataManager.getInstance().selfRampagePointLevel = int(param1.ownerRampagePointLevel);
         }
         DataManager.getInstance().swfManager.changeToMiniMode();
         if(param1.sysTime != null && param1.sysTime != "")
         {
            Data.instance.time.updateServerTime(String(param1.sysTime));
         }
         if(Data.instance.isEditMode)
         {
            Data.instance.isEditMode = false;
         }
         if(this.mainUI == null)
         {
            this.mainUI = new TownUIPanel();
            this.mainUI.reset();
            this.mainUI.addEventListener("showCitizenList",this.onClickCitizenListBt);
            this.mainUI.addEventListener("showCardModule",this.onClickCardBt);
            this.mainUI.addEventListener("gotoItemShop",this.onClickItemShopBt);
            this.mainUI.addEventListener("gotoRamPage",this.onSelRampageMode);
            this.mainUI.addEventListener(MyEvent.SHOW_BAG_ITEM_LIST,this.onClickBagBt);
         }
         var _loc3_:Array = param1.grounds as Array;
         if(_loc3_ == null)
         {
            trace("[DEBUG-DATA-MISSING] param1.grounds was null in onGetUserTownInfo - using empty fallback");
            _loc3_ = [];
         }
         var _loc4_:Array = [];
         var _loc5_:* = _loc3_.length - 1;
         while(_loc5_ >= 0)
         {
            _loc4_.push(Data.instance.areaTileItemIdConf[_loc3_[_loc5_]]);
            _loc5_--;
         }
         Data.instance.opendAreaTileList = _loc4_;
         Data.instance.map.reset(GameConfig.DEFAULT_BG_ID);
         if(Data.instance.tileIndexMapArr == null)
         {
            Data.instance.tools.createTileMapArr();
         }
         Data.instance.manager.reset();
         if(param1.buildings == null)
         {
            param1.buildings = [];
         }
         var _loc6_:Array = param1.buildings as Array;
         if(param1.decorations != null)
         {
            _loc6_ = _loc6_.concat(param1.decorations as Array);
         }
         else
         {
            param1.decorations = [];
         }
         if(param1.plants != null)
         {
            _loc6_ = _loc6_.concat(param1.plants as Array);
         }
         else
         {
            param1.plants = [];
         }
         Data.instance.manager.createTownBuildList(_loc6_);
         this.mainUI.setData(param1);
         if(this.friendBonusPanel != null)
         {
            this.friendBonusPanel.hide();
            this.friendBonusPanel = null;
         }
         this.welcomePanel.hide();
         var _loc7_:int = int(param1.addEnergy);
         if(_loc7_ == 0)
         {
            this.welcomePanel.show();
         }
         else
         {
            _loc12_ = FriendManager.instance.getFriendVO(Data.instance.townOwnerId);
            _loc13_ = _loc12_ != null ? _loc12_.name : "";
            _loc14_ = Lang.getLocalizationString(Lang.UI,Lang.TOWN,"TOWN_NAME",_loc13_);
            this.friendBonusPanel = new FriendBonusPanel();
            this.friendBonusPanel.reset(_loc14_,_loc7_);
            this.friendBonusPanel.showPanel();
         }
         if(_loc2_)
         {
            setTimeout(this.showTownMovie,1);
            DataManager.getInstance().dispatchEvent(new MyEvent(MyEvent.SHOW_FRIEND_LIST,{
               "isShow":true,
               "id":Data.instance.townOwnerId
            }));
         }
         else
         {
            this.showTownMovie();
         }
         var _loc8_:Array = Data.instance.getProperty("tdEventArr");
         if(_loc8_ != null && _loc8_.length > 0)
         {
            _loc5_ = 0;
            while(_loc5_ < _loc8_.length)
            {
               _loc15_ = _loc8_[_loc5_];
               DataManager.getInstance().questCheckSWFDO.dispatchEvent(new MyEvent(_loc15_[0],_loc15_[1]));
               _loc5_++;
            }
            Data.instance.setProperty("tdEventArr",null);
         }
         var _loc9_:String = Data.instance.getProperty("defaultScreen");
         if(_loc9_ == "mission")
         {
            if(DataManager.getInstance().houseMissionMap != null)
            {
               this.onSelMissionMode(null);
            }
            Data.instance.setProperty("defaultScreen",null);
         }
         if(Data.instance.isMySelf)
         {
            TownEntry.getCityFuncHouseData();
         }
         Data.instance.map.getBaseMap().resetUnLockBtList();
         Data.instance.map.getBaseMap().resetBizItem();
         if(DataManager.getInstance().houseMissionMap != null)
         {
            this.resetRampageBt();
         }
         if(this.isFirstLogInTown)
         {
            this.isFirstLogInTown = false;
            SoundManager.instance.createMusic(DataManager.getInstance().musicList[SoundManager.TOWN_BG]);
            SoundManager.instance.loadMusic([DataManager.getInstance().musicList[SoundManager.TOWN_BG]]);
         }
         if(!Data.instance.isCompleteTutorial)
         {
            trace("[DEBUG-TUTORIAL] onGetUserTownInfo: isCompleteTutorial=false, tutorialStep=" + DataManager.getInstance().commonModel.tutorialStep + " (START=" + DataManager.TUTORIAL_STEP_START + ")");
            if(DataManager.getInstance().commonModel.tutorialStep != DataManager.TUTORIAL_STEP_START)
            {
               trace("[DEBUG-TUTORIAL] onGetUserTownInfo: calling tutorial.reset()");
               this.tutorial.reset();
            }
            else if(Config.OFFLINE_MODE)
            {
               trace("[DEBUG-TUTORIAL] onGetUserTownInfo: tutorialStep==START and OFFLINE_MODE - this branch does nothing, tutorial will never start from here");
            }
         }
         else if(Data.instance.getProperty("lastGameModule") == "adventure")
         {
            this.tutorial.reset();
            Data.instance.setProperty("lastGameModule",null);
            return;
         }
      }
      
      public function setUserControlActive() : void
      {
         var _loc3_:* = 0;
         var _loc4_:* = 0;
         var _loc9_:Sprite = null;
         var _loc10_:Array = null;
         var _loc11_:int = 0;
         var _loc12_:int = 0;
         var _loc13_:* = 0;
         var _loc14_:* = 0;
         var _loc15_:Building = null;
         var _loc16_:Building = null;
         Data.instance.isCompleteTutorial = true;
         var _loc1_:Array = Data.instance.manager.getAllItemArr();
         var _loc2_:Array = [];
         _loc3_ = Data.instance.townMaxRow - 1;
         while(_loc3_ >= 0)
         {
            _loc2_[_loc3_] = [];
            _loc4_ = Data.instance.townMaxLine - 1;
            while(_loc4_ >= 0)
            {
               if(_loc2_[_loc3_][_loc4_] != -1)
               {
                  _loc2_[_loc3_][_loc4_] = -1;
               }
               _loc4_--;
            }
            _loc3_--;
         }
         var _loc5_:Array = Data.instance.opendAreaTileList;
         var _loc6_:int = int(Data.instance.areaTilePosConf.length);
         var _loc7_:* = 0;
         while(_loc7_ < _loc6_)
         {
            if(_loc5_.indexOf(_loc7_) != -1)
            {
               _loc10_ = Data.instance.areaTilePosConf[_loc7_];
               _loc13_ = Data.instance.areaTileHeight - 1;
               while(_loc13_ >= 0)
               {
                  _loc11_ = _loc10_[0] + _loc13_;
                  _loc14_ = Data.instance.areaTileWidth - 1;
                  while(_loc14_ >= 0)
                  {
                     _loc12_ = _loc10_[1] + _loc14_;
                     if(_loc2_[_loc11_][_loc12_] != 0)
                     {
                        _loc2_[_loc11_][_loc12_] = 0;
                     }
                     _loc14_--;
                  }
                  _loc13_--;
               }
            }
            _loc7_++;
         }
         _loc7_ = _loc1_.length - 1;
         while(_loc7_ >= 0)
         {
            if(_loc1_[_loc7_] is Building)
            {
               _loc15_ = _loc1_[_loc7_];
               if(_loc2_[_loc15_.getRow()][_loc15_.getLine()] == -1)
               {
                  _loc15_.setMouseEventAble(false);
               }
               else
               {
                  _loc15_.setMouseEventAble(true);
               }
            }
            _loc7_--;
         }
         _loc1_ = Data.instance.manager.getRoadItemArr();
         _loc7_ = _loc1_.length - 1;
         while(_loc7_ >= 0)
         {
            if(_loc1_[_loc7_] is Building)
            {
               _loc16_ = _loc1_[_loc7_];
               if(_loc2_[_loc16_.getRow()][_loc16_.getLine()] == -1)
               {
                  _loc16_.setMouseEventAble(false);
               }
               else
               {
                  _loc16_.setMouseEventAble(true);
               }
            }
            _loc7_--;
         }
         var _loc8_:Sprite = this.mainUI.getSkin().getChildByName("btListMc") as Sprite;
         _loc9_ = _loc8_.getChildByName("shopBt") as Sprite;
         _loc9_.visible = true;
         _loc9_ = _loc8_.getChildByName("citizenBt") as Sprite;
         _loc9_.visible = true;
         _loc9_ = _loc8_.getChildByName("cardBt") as Sprite;
         _loc9_.visible = true;
         _loc9_ = _loc8_.getChildByName("bagBt") as Sprite;
         _loc9_.visible = true;
         this.resetRampageBt();
      }
   }
}

