package com.popcap.pvz
{
   import caurina.transitions.properties.ColorShortcuts;
   import caurina.transitions.properties.CurveModifiers;
   import caurina.transitions.properties.FilterShortcuts;
   import com.popcap.framework.components.YToolTips;
   import com.popcap.framework.core.CommonModel;
   import com.popcap.framework.core.EnterFrame;
   import com.popcap.framework.core.Lang;
   import com.popcap.framework.crypto.EncryptTool;
   import com.popcap.framework.events.MyEvent;
   import com.popcap.framework.managers.DataManager;
   import com.popcap.framework.managers.FunctionBuildingManager;
   import com.popcap.framework.managers.PropItemsManager;
   import com.popcap.framework.managers.RemindManager;
   import com.popcap.framework.managers.SwfManager;
   import com.popcap.framework.net.MyCookie;
   import com.popcap.framework.net.PVZNetConnection;
   import com.popcap.framework.net.TxtLoader;
   import com.popcap.framework.panel.CardViewer;
   import com.popcap.framework.panel.ChangeScenePanel;
   import com.popcap.framework.panel.UpGradePanel;
   import com.popcap.framework.uis.Waiting;
   import com.popcap.framework.utils.Debug;
   import com.popcap.framework.utils.HashMap;
   import com.popcap.framework.utils.KeyboardManager;
   import com.popcap.framework.utils.MyEnterFrame;
   import com.popcap.framework.utils.MySystem;
   import com.popcap.framework.utils.Reflection;
   import com.popcap.framework.utils.StringUtils;
   import com.popcap.pvz.adventure.AdventureGame;
   import com.popcap.pvz.common.MissionConfigParser;
   import com.popcap.pvz.common.PVZDataLocator;
   import com.popcap.pvz.common.PVZSwfLoader;
   import com.popcap.pvz.common.PVZXmlLoader;
   import com.popcap.pvz.common.PVZXmlParser;
   import com.popcap.pvz.common.ResourceCache;
   import com.popcap.pvz.common.conf.PVZConfig;
   import com.popcap.pvz.common.conf.ZombiesConfig;
   import com.popcap.pvz.common.control.BasicGame;
   import com.popcap.pvz.common.model.dic.CardsFactory;
   import com.popcap.pvz.common.model.dic.PlantsFactory;
   import com.popcap.pvz.common.model.vos.card.CardVO;
   import com.popcap.pvz.common.utils.TDFunctionBuildingUtils;
   import com.popcap.pvz.rampage.RamPageGame;
   import com.popcap.town.data.Data;
   import com.popcap.town.manager.BldSkinManager;
   import com.popcap.town.manager.ServerTime;
   import com.popcap.framework.core.Config;
   import flash.display.Bitmap;
   import flash.display.DisplayObjectContainer;
   import flash.display.MovieClip;
   import flash.display.Sprite;
   import flash.events.Event;
   import flash.external.ExternalInterface;
   import flash.geom.Rectangle;
   import flash.net.URLLoader;
   import flash.net.URLRequest;
   import flash.system.Security;
   import flash.utils.setTimeout;
   
   public class PVZEntry extends Sprite
   {
      
      private var isXmlLoadComplete:Boolean;
      
      private var missionLoader:URLLoader;
      
      private var missionXML:XML;
      
      private var game:BasicGame;
      
      private var debugMission:Object;
      
      private var townDebugXml:XML;
      
      private var debugXml:XML;
      
      private var _revealSp:Sprite;
      
      private var _revealBmp:Bitmap;
      
      private var _revealT:int;
      
      public function PVZEntry()
      {
         var _loc1_:String = null;
         var _loc2_:URLRequest = null;
         var _loc3_:TxtLoader = null;
         var _loc4_:String = null;
         var _loc5_:int = 0;
         this.townDebugXml = <childModule moduleName="newTD" label="城镇模块主程序" swfId="PVZEntry.swf" src="" entry="enterModule">
				</childModule>;
         this.debugXml = <childModule moduleName="newTD" label="城镇模块主程序" swfId="PVZEntry.swf" src="" entry="enterModule">
				<commonResource>
					<!--公共资源-->
					<resource swfId="pvzTDSound" label="td音效文件"/>
					<!--resource swfId="pvzZombie" label="僵尸资源文件"/-->
					<resource swfId="pvzPlant" label="植物资源文件"/>
					<resource swfId="pvzBullet" label="动画效果资源文件"/>
					<!--resource swfId="pvzCharmZombie" label="动画效果资源文件"/-->
					<!--resource swfId="pvzBalloonZombie" label="气球僵尸资源"/-->
					<resource swfId="ui" label="动画效果资源文件"/>
					<resource label="公共资源" swfId="ZenGarden"/>
				</commonResource>
				<rampageConfig>
					<step level="1-3" groupVaseQty="10" rushCoolDown="12" allowedRampageCard="10008:40,10002:40,10009:10,10003:10" initVase="3" dropVaseCD="16" dropVaseNum="0"></step>
					<step level="4-5" groupVaseQty="20" rushCoolDown="10" allowedRampageCard="10008:25,10002:25,10009:24,10003:24,10005:2" initVase="3" dropVaseCD="8" dropVaseNum="1"></step>
					<step level="6-8" groupVaseQty="30" rushCoolDown="9" allowedRampageCard="10005:5,10009:30,10003:30,10007:5,10008:15,10002:15" initVase="4" dropVaseCD="8" dropVaseNum="1"></step>
					<step level="9-12" groupVaseQty="40" rushCoolDown="8" allowedRampageCard="10005:5,10009:20,10010:10,10003:20,10007:5,10008:20,10002:20" initVase="4" dropVaseCD="8" dropVaseNum="1"></step>
					<step level="13-90" groupVaseQty="50" rushCoolDown="8" allowedRampageCard="10005:5,10009:20,10010:10,10003:20,10004:10,10007:5,10008:15,10002:15" initVase="5" dropVaseCD="8" dropVaseNum="1"></step>
				</rampageConfig>
				<!--新手奖励经验和金钱-->
				<tutorial money_prize="2000" exp_prize="99" tutorial1Card="2" tutorial2Card="12"/>
				<screens>
					<!--
						 场景主题
						 如果有特殊的属性可以放这里.
						 这里要和上面的分开的原因是因为,这里的swf是按需加载的,而上面的是全部加载;
					-->
					<screen id="1" label="白天前院" swfId="pvzScreen1"/>
					<screen id="2" label="夜晚前院" swfId="pvzScreen2"/>
					<screen id="3" label="白天水池" swfId="pvzScreen3"/>
					<screen id="4" label="夜晚水池" swfId="pvzScreen4"/>
					<screen id="5" label="白天屋顶" swfId="pvzScreen5"/>
					<screen id="6" label="夜晚屋顶" swfId="pvzScreen6"/>
				</screens>
				<tdMode mode="1" name="Adventure">
					<!--冒险模式用到的资源,会根据游戏模式单独加载-->
					<resource swfId="pvzUI" label="冒险模式ui资源文件"/>
				</tdMode>
				<tdMode mode="2" name="RamPage">
					<resource swfId="pvzUI" label="冒险模式ui资源文件"/>
				</tdMode>
				<tdMode mode="3" name="Adventure">
					<resource swfId="pvzUI" label="冒险模式ui资源文件"/>
				</tdMode>
				<tdMode mode="4" name="Adventure">
					<resource swfId="pvzUI" label="冒险模式ui资源文件"/>
				</tdMode>
				<tdMode mode="5" name="Adventure">
					<resource swfId="pvzUI" label="冒险模式ui资源文件"/>
				</tdMode>
				<tdMode mode="102" name="Rampage">
					<resource swfId="pvzUI" label="冒险模式ui资源文件"/>
				</tdMode>
				<tdMode mode="103" name="Rampage">
					<resource swfId="pvzUI" label="冒险模式ui资源文件"/>
				</tdMode>
			</childModule>;
         super();
         if(PVZConfig.TD_OFFLINE_MODE)
         {
            Debug.isDebug = true;
            Security.allowDomain("*");
            Security.allowInsecureDomain("*");
            stage.scaleMode = "noScale";
            stage.align = "TL";
            this.addEventListener(Event.ADDED_TO_STAGE,this.onAddToStageInDebugMode);
            this.missionLoader = new URLLoader();
            _loc1_ = "debug_mission";
            if(!PVZConfig.TD_OFFLINE_MODE)
            {
               _loc4_ = ExternalInterface.call("window.location.href.toString");
               if(_loc4_ != null && _loc4_.indexOf("level=") != -1)
               {
                  _loc5_ = _loc4_.indexOf("level=");
                  _loc1_ = _loc4_.substring(_loc5_ + 6,_loc4_.length);
               }
            }
            KeyboardManager.listener = stage;
            EnterFrame.linstener = this;
            Debug.init(this);
            Debug.trace("xml.url==",_loc1_,"::::",_loc4_);
            _loc2_ = new URLRequest(_loc1_ + ".xml");
            this.missionLoader.load(_loc2_);
            this.missionLoader.addEventListener(Event.COMPLETE,this.onLoadMissionComplete);
            _loc3_ = new TxtLoader();
            _loc3_.addEventListener(MyEvent.LOAD_COMPLETE,this.onLangLoaded);
            _loc3_.load("conf/Localization.xml");
         }
      }
      
      private function onLangLoaded(param1:MyEvent) : void
      {
         var _loc2_:XML = new XML(param1.data.content);
         Lang.instance = _loc2_;
      }
      
      private function onLoadMissionComplete(param1:Event) : void
      {
         this.missionXML = new XML(this.missionLoader.data);
         this.debugMission = {};
         this.debugMission.type = int(this.missionXML.type);
         this.debugMission.scene = int(this.missionXML.scene);
         this.debugMission.totalWaves = int(this.missionXML.totalWaves);
         this.debugMission.initSun = int(this.missionXML.initSun);
         this.debugMission.initTomb = int(this.missionXML.initTomb);
         this.debugMission.allowedZombies = String(this.missionXML.allowedZombies).split(",");
         this.debugMission.flagWave = String(this.missionXML.flagWave);
         this.debugMission.difficultCoefficient = int(this.missionXML.difficultCoefficient);
         this.debugMission.initPlant = String(this.missionXML.initPlant);
         this.debugMission.cardCdDiscount = Number(this.missionXML.cardCdDiscount);
         this.debugMission.missionName = "debug_mission";
         this.debugMission.gameDuration = int(this.missionXML.gameDuration);
         this.debugMission.rushCoolDown = int(this.missionXML.rushCoolDown);
         this.debugMission.isZombieWhackable = int(this.missionXML.isZombieWhackable);
         this.enterModule(this.debugXml,this.debugMission);
      }
      
      public function enterModule(param1:XML, ... rest) : void
      {
         var _loc5_:Object = null;
         var _loc6_:int = 0;
         var _loc7_:Object = null;
         Debug.trace("NEW_TD_EnterModule:",param1.toXMLString(),StringUtils.toString(rest));
         PVZDataLocator.instance.configXml = param1;
         if(rest[1] != null)
         {
            _loc5_ = rest[1];
            if(_loc5_ != null)
            {
               PVZDataLocator.instance.currBattleHousePosition = _loc5_.tdHouseId;
               PVZDataLocator.instance.battleSoldierId = _loc5_.tdSoldierId;
               PVZDataLocator.instance.currBattleBuildingId = _loc5_.tdBuildingId;
            }
         }
         DataManager.getInstance().stage.frameRate = PVZConfig.FRAMERATE;
         var _loc3_:MissionConfigParser = new MissionConfigParser();
         var _loc4_:Object = rest[0];
         if(_loc4_ == null)
         {
            _loc4_ = PVZConfig.MISSION_TUTORIAL1;
         }
         if(PVZConfig.TD_OFFLINE_MODE)
         {
            _loc4_.vaseZombieWeight = 1;
            _loc4_.vaseCardWeight = 2;
            _loc4_.vasePlantWeight = 2;
            _loc3_.parseMissionObject(_loc4_);
         }
         else if(_loc4_.type == PVZConfig.GAME_MODE_RAMPAGE_TUTORIAL)
         {
            _loc4_ = PVZConfig.MISSION_TUTORIAL_RAMPAGE;
            _loc3_.parseMissionObject(_loc4_);
         }
         else if(_loc4_.type == PVZConfig.GAME_MODE_RAMPAGE || _loc4_.type == PVZConfig.GAME_MODE_RAMPAGE_CAPTURE)
         {
            _loc6_ = int(DataManager.getInstance().pvzData.currentTournamentId);
            if(_loc4_.type == PVZConfig.GAME_MODE_RAMPAGE_CAPTURE)
            {
               PVZDataLocator.instance.captureType = rest[2];
            }
            _loc7_ = DataManager.getInstance().pvzData.tournaments[_loc6_];
            _loc7_.type = _loc4_.type;
            _loc3_.parseMissionObject(_loc7_);
         }
         else
         {
            _loc3_.parseMissionObject(_loc4_);
         }
         if(PVZConfig.TD_OFFLINE_MODE)
         {
            this.loadXML();
         }
         else if(DataManager.getInstance().upgradeCard == null)
         {
            PVZNetConnection.getInstance().sendAndCall("services.I5013",this.onGetCardUpgradeInfo);
         }
         else
         {
            this.loadXML();
         }
      }
      
      private function onGetCardUpgradeInfo(param1:Object) : void
      {
         DataManager.getInstance().upgradeCard = param1.list;
         if(DataManager.getInstance().upgradeCard == null)
         {
            DataManager.getInstance().upgradeCard = new Object();
         }
         this.loadXML();
      }
      
      private function loadXML() : void
      {
         var _loc2_:PVZXmlLoader = null;
         var _loc3_:PVZXmlParser = null;
         var _loc4_:PVZXmlLoader = null;
         if(!this.isXmlLoadComplete)
         {
            _loc2_ = new PVZXmlLoader();
            _loc2_.addEventListener(MyEvent.SUCCESS,this.loadXmlComplete);
            _loc2_.loadXmlFiles();
         }
         else
         {
            _loc3_ = new PVZXmlParser();
            _loc4_ = new PVZXmlLoader();
            _loc4_.plantXml = DataManager.getInstance().plantDataXml;
            _loc3_.dicParser(_loc4_);
         }
         var _loc1_:PVZSwfLoader = new PVZSwfLoader();
         _loc1_.addEventListener(MyEvent.LOAD_COMPLETE,this.onSwfLoadedComplete);
         _loc1_.loadSwfFiles(PVZDataLocator.instance.configXml,PVZDataLocator.instance.gameMode);
         PVZDataLocator.instance.doc = this;
         EnterFrame.pause = false;
      }
      
      private function onSwfLoadedComplete(param1:MyEvent = null) : void
      {
         if(param1 != null)
         {
            param1.currentTarget.removeEventListener(MyEvent.SUCCESS,this.onSwfLoadedComplete);
         }
         if(this.isXmlLoadComplete)
         {
            this.startFlow();
         }
      }
      
      private function loadXmlComplete(param1:MyEvent = null) : void
      {
         if(param1 != null)
         {
            param1.currentTarget.removeEventListener(MyEvent.SUCCESS,this.loadXmlComplete);
         }
         this.isXmlLoadComplete = true;
         if(ResourceCache.instance.getCommonResourceApp() != null && ResourceCache.instance.getUIResourceApp() != null)
         {
            this.startFlow();
         }
      }
      
      private function startFlow() : void
      {
         var _loc3_:Array = null;
         var _loc4_:MovieClip = null;
         var _loc5_:CardVO = null;
         if(PVZConfig.TD_OFFLINE_MODE)
         {
            DataManager.getInstance().waiting = new Waiting(DataManager.getInstance().uiContainer);
            DataManager.getInstance().commonModel = new CommonModel();
            DataManager.getInstance().commonModel.expCache = 100;
            DataManager.getInstance().commonModel.moneyCache = 10000;
            DataManager.getInstance().commonModel.levelCache = 9;
            DataManager.getInstance().commonModel.refreshDataFromCache();
            DataManager.getInstance().isNight = false;
            Data.instance.confXml = this.townDebugXml;
            Data.instance.skinManager = new BldSkinManager();
            _loc3_ = [];
            _loc4_ = ResourceCache.instance.getMovieClilp("functionBldArrowMc");
            FunctionBuildingManager.instance.setArrowSkin(_loc4_);
            FunctionBuildingManager.instance.setData(_loc3_);
            DataManager.getInstance().swfManager.setApplicationDomain(SwfManager.UI_LIBRARY,ResourceCache.instance.getCommonResourceApp());
            DataManager.getInstance().upGradePanel = new UpGradePanel();
            DataManager.getInstance().cardViewer = new CardViewer();
            DataManager.getInstance().setPopupLayer();
            DataManager.getInstance().changeScenePanel = new ChangeScenePanel();
            RemindManager.instance;
            DataManager.getInstance().daveThread = new MyEnterFrame();
            DataManager.getInstance().daveThread.linstener = stage;
            PVZDataLocator.instance.doc.addEventListener(MyEvent.EXIT_MODULE,this.onSelectedExitModule);
            DataManager.getInstance().daveThread = new MyEnterFrame();
            DataManager.getInstance().daveThread.linstener = this;
         }
         PVZDataLocator.instance.uiContainer = DataManager.getInstance().uiContainer;
         YToolTips.init(DataManager.getInstance().topContainer);
         TDFunctionBuildingUtils.instance.reset();
         this.dispatchEvent(new MyEvent(MyEvent.ENTRY_MODULE_COMPLETE));
         DataManager.getInstance().swfManager.setLoadingVisible(false);
         var _loc1_:Array = CardsFactory.getInstance().getCards();
         var _loc2_:int = 0;
         while(_loc2_ < _loc1_.length)
         {
            _loc5_ = _loc1_[_loc2_];
            _loc5_.totalCoolDownTime *= PVZDataLocator.instance.missionVO.cardCdDiscount;
            _loc2_++;
         }
         switch(PVZDataLocator.instance.gameMode)
         {
            case PVZConfig.GAME_MODE_ADVENTURE:
               this.game = new AdventureGame();
               break;
            case PVZConfig.GAME_MODE_RAMPAGE:
            case PVZConfig.GAME_MODE_RAMPAGE_CAPTURE:
            case PVZConfig.GAME_MODE_RAMPAGE_TUTORIAL:
               this.game = new RamPageGame();
               break;
            default:
               this.game = new AdventureGame();
         }
         this.game.init();
         this.playLevelReveal();
         if(!PVZConfig.TD_OFFLINE_MODE)
         {
            setTimeout(DataManager.getInstance().waiting.hide,1000);
            dispatchEvent(new MyEvent(MyEvent.ENTRY_MODULE_COMPLETE));
            DataManager.getInstance().dispatchEvent(new Event(DataManager.EVENT_TYPE_CHANGESCENE));
         }
         DataManager.getInstance().doc.scrollRect = null;
      }
      
      private function playLevelReveal() : void
      {
         var _loc1_:Bitmap = null;
         var _loc2_:DisplayObjectContainer = null;
         try
         {
            _loc1_ = ResourceCache.instance.getBitmap("SunflowerTransition");
            if(_loc1_ == null)
            {
               return;
            }
            _loc2_ = DataManager.getInstance().topContainer;
            if(_loc2_ == null)
            {
               _loc2_ = stage;
            }
            if(_loc2_ == null)
            {
               return;
            }
            this.stopLevelReveal();
            this._revealSp = new Sprite();
            this._revealSp.mouseEnabled = false;
            this._revealSp.mouseChildren = false;
            _loc1_.smoothing = true;
            this._revealBmp = _loc1_;
            this._revealSp.addChild(_loc1_);
            _loc2_.addChild(this._revealSp);
            this._revealT = 0;
            this._revealSp.addEventListener(Event.ENTER_FRAME,this.onRevealFrame);
            this.onRevealFrame(null);
         }
         catch(err:Error)
         {
            this.stopLevelReveal();
         }
      }
      
      private function onRevealFrame(param1:Event) : void
      {
         var _loc2_:Number = Config.STAGE_WIDTH > 0 ? Number(Config.STAGE_WIDTH) : 760;
         var _loc3_:Number = Config.STAGE_HEIGHT > 0 ? Number(Config.STAGE_HEIGHT) : 600;
         var _loc4_:int = 6;
         var _loc5_:int = 42;
         var _loc6_:Number = 0;
         var _loc7_:Number = 0.02;
         var _loc8_:Number = NaN;
         var _loc9_:Number = NaN;
         var _loc10_:Number = NaN;
         var _loc11_:Number = NaN;
         if(this._revealSp == null || this._revealBmp == null)
         {
            return;
         }
         if(this._revealSp.parent != null)
         {
            this._revealSp.parent.setChildIndex(this._revealSp,this._revealSp.parent.numChildren - 1);
         }
         if(this._revealT > _loc4_)
         {
            _loc6_ = Math.min(1,(this._revealT - _loc4_) / _loc5_);
            _loc7_ = 0.02 + _loc6_ * _loc6_ * 3.4;
         }
         this._revealBmp.scaleX = this._revealBmp.scaleY = _loc7_;
         _loc8_ = this._revealBmp.bitmapData.width * _loc7_;
         _loc9_ = this._revealBmp.bitmapData.height * _loc7_;
         _loc10_ = _loc2_ / 2 - _loc8_ / 2;
         _loc11_ = _loc3_ / 2 - _loc9_ / 2;
         this._revealBmp.x = _loc10_;
         this._revealBmp.y = _loc11_;
         this._revealSp.graphics.clear();
         this._revealSp.graphics.beginFill(0,1);
         if(_loc11_ > 0)
         {
            this._revealSp.graphics.drawRect(-20,-20,_loc2_ + 40,_loc11_ + 21);
         }
         if(_loc11_ + _loc9_ < _loc3_)
         {
            this._revealSp.graphics.drawRect(-20,_loc11_ + _loc9_ - 1,_loc2_ + 40,_loc3_ - (_loc11_ + _loc9_) + 21);
         }
         if(_loc10_ > 0)
         {
            this._revealSp.graphics.drawRect(-20,_loc11_,_loc10_ + 21,_loc9_);
         }
         if(_loc10_ + _loc8_ < _loc2_)
         {
            this._revealSp.graphics.drawRect(_loc10_ + _loc8_ - 1,_loc11_,_loc2_ - (_loc10_ + _loc8_) + 21,_loc9_);
         }
         this._revealSp.graphics.endFill();
         this._revealSp.alpha = _loc6_ > 0.7 ? Math.max(0,1 - (_loc6_ - 0.7) / 0.3) : 1;
         ++this._revealT;
         if(_loc6_ >= 1)
         {
            this.stopLevelReveal();
         }
      }
      
      private function stopLevelReveal() : void
      {
         if(this._revealSp != null)
         {
            this._revealSp.removeEventListener(Event.ENTER_FRAME,this.onRevealFrame);
            this._revealSp.graphics.clear();
            if(this._revealSp.parent != null)
            {
               this._revealSp.parent.removeChild(this._revealSp);
            }
         }
         this._revealSp = null;
         this._revealBmp = null;
      }
      
      public function removeModule() : void
      {
         this.stopLevelReveal();
         DataManager.getInstance().doc.scrollRect = new Rectangle(0,0,760,600);
         this.game.dispose();
         this.game = null;
         PlantsFactory.getInstance().reset();
         CardsFactory.getInstance().reset();
         ResourceCache.instance.dispose();
         PVZDataLocator.instance.gameContainer = null;
         PVZDataLocator.instance.mainContainer = null;
         PVZDataLocator.instance.topContainer = null;
         PVZDataLocator.instance.bottomContainer = null;
         PVZDataLocator.instance.uiContainer = null;
         MySystem.gc();
         if(PVZConfig.TD_OFFLINE_MODE)
         {
            setTimeout(this.enterModule,3000,this.debugXml,this.debugMission);
         }
      }
      
      private function onSelectedExitModule(param1:MyEvent) : void
      {
         this.removeModule();
      }
      
      private function onAddToStageInDebugMode(param1:Event) : void
      {
         var _loc17_:Array = null;
         removeEventListener(Event.ADDED_TO_STAGE,this.onAddToStageInDebugMode);
         var _loc2_:Sprite = this;
         DataManager.getInstance().root = _loc2_;
         DataManager.getInstance().moduleContainer = _loc2_.addChild(new Sprite()) as Sprite;
         DataManager.getInstance().uiContainer = _loc2_.addChild(new Sprite()) as Sprite;
         DataManager.getInstance().topContainer = _loc2_.addChild(new Sprite()) as Sprite;
         YToolTips.init(DataManager.getInstance().topContainer);
         var _loc3_:Object = {};
         var _loc4_:Object = {};
         _loc4_["plantData"] = "conf/PlantData.xml";
         _loc4_["zombieData"] = "conf/ZombieData.xml";
         _loc4_["BoostData"] = "conf/BoostData.xml";
         _loc4_["pvzBulletData"] = "pvz/conf/pvzBulletData.xml";
         _loc4_["PropData"] = "conf/PropData.xml";
         DataManager.getInstance().xmlList = _loc4_;
         _loc3_["zombieData"] = "zombieData/";
         _loc3_["plantData"] = "plantData/";
         _loc3_["popcapData"] = "popcapData/";
         DataManager.getInstance().cryptoList = _loc3_;
         DataManager.getInstance().md5FileId = "";
         var _loc5_:Object = {};
         _loc5_["pvzTDSound"] = "pvz/pvzTDSound.swf";
         _loc5_["pvzPlant"] = "pvz/pvzPlant.swf";
         _loc5_["pvzBullet"] = "pvz/pvzBullet.swf";
         _loc5_["pvzUI"] = "pvz/pvzUI.swf";
         _loc5_["ui"] = "public/ui.swf";
         _loc5_["ZenGarden"] = "gardenSource/ZenGarden.swf";
         _loc5_["pvzScreen1"] = "pvz/screen/pvzScreen1.swf";
         _loc5_["pvzScreen2"] = "pvz/screen/pvzScreen2.swf";
         _loc5_["pvzScreen3"] = "pvz/screen/pvzScreen3.swf";
         _loc5_["pvzScreen4"] = "pvz/screen/pvzScreen4.swf";
         _loc5_["pvzScreen5"] = "pvz/screen/pvzScreen5.swf";
         _loc5_["building"] = "pvz/town/building.swf";
         _loc5_["rampageUI"] = "pvz/rampageUI.swf";
         _loc5_["itemShop"] = "itemShop.swf";
         var _loc6_:String = "pvz/zombies/";
         _loc5_[ZombiesConfig.ZOMBIE_SWF_MAP[ZombiesConfig.ZOMBIE_NORMAL]] = _loc6_ + ZombiesConfig.ZOMBIE_SWF_MAP[ZombiesConfig.ZOMBIE_NORMAL] + ".swf";
         _loc5_[ZombiesConfig.ZOMBIE_SWF_MAP[ZombiesConfig.ZOMBIE_SNORKEL]] = _loc6_ + ZombiesConfig.ZOMBIE_SWF_MAP[ZombiesConfig.ZOMBIE_SNORKEL] + ".swf";
         _loc5_[ZombiesConfig.ZOMBIE_SWF_MAP[ZombiesConfig.ZOMBIE_POLEVAULTER]] = _loc6_ + ZombiesConfig.ZOMBIE_SWF_MAP[ZombiesConfig.ZOMBIE_POLEVAULTER] + ".swf";
         _loc5_[ZombiesConfig.ZOMBIE_SWF_MAP[ZombiesConfig.ZOMBIE_DOLPHIN_RIDER]] = _loc6_ + ZombiesConfig.ZOMBIE_SWF_MAP[ZombiesConfig.ZOMBIE_DOLPHIN_RIDER] + ".swf";
         _loc5_[ZombiesConfig.ZOMBIE_SWF_MAP[ZombiesConfig.ZOMBIE_NEWSPAPER]] = _loc6_ + ZombiesConfig.ZOMBIE_SWF_MAP[ZombiesConfig.ZOMBIE_NEWSPAPER] + ".swf";
         _loc5_[ZombiesConfig.ZOMBIE_SWF_MAP[ZombiesConfig.ZOMBIE_FOOTBALL]] = _loc6_ + ZombiesConfig.ZOMBIE_SWF_MAP[ZombiesConfig.ZOMBIE_FOOTBALL] + ".swf";
         _loc5_[ZombiesConfig.ZOMBIE_SWF_MAP[ZombiesConfig.ZOMBIE_JACK_IN_THE_BOX]] = _loc6_ + ZombiesConfig.ZOMBIE_SWF_MAP[ZombiesConfig.ZOMBIE_JACK_IN_THE_BOX] + ".swf";
         _loc5_[ZombiesConfig.ZOMBIE_SWF_MAP[ZombiesConfig.ZOMBIE_GARGANTUAR]] = _loc6_ + ZombiesConfig.ZOMBIE_SWF_MAP[ZombiesConfig.ZOMBIE_GARGANTUAR] + ".swf";
         _loc5_[ZombiesConfig.ZOMBIE_SWF_MAP[ZombiesConfig.ZOMBIE_CHINESE]] = _loc6_ + ZombiesConfig.ZOMBIE_SWF_MAP[ZombiesConfig.ZOMBIE_CHINESE] + ".swf";
         _loc5_[ZombiesConfig.ZOMBIE_SWF_MAP[ZombiesConfig.ZOMBIE_DANCER]] = _loc6_ + ZombiesConfig.ZOMBIE_SWF_MAP[ZombiesConfig.ZOMBIE_DANCER] + ".swf";
         _loc5_[ZombiesConfig.ZOMBIE_SWF_MAP[ZombiesConfig.ZOMBIE_ZAMBONI]] = _loc6_ + ZombiesConfig.ZOMBIE_SWF_MAP[ZombiesConfig.ZOMBIE_ZAMBONI] + ".swf";
         _loc5_[ZombiesConfig.ZOMBIE_SWF_MAP[ZombiesConfig.ZOMBIE_BOBSLED]] = _loc6_ + ZombiesConfig.ZOMBIE_SWF_MAP[ZombiesConfig.ZOMBIE_BOBSLED] + ".swf";
         _loc5_[ZombiesConfig.ZOMBIE_SWF_MAP[ZombiesConfig.ZOMBIE_BALLON]] = _loc6_ + ZombiesConfig.ZOMBIE_SWF_MAP[ZombiesConfig.ZOMBIE_BALLON] + ".swf";
         _loc5_[ZombiesConfig.ZOMBIE_SWF_MAP[ZombiesConfig.ZOMBIE_DIGGER]] = _loc6_ + ZombiesConfig.ZOMBIE_SWF_MAP[ZombiesConfig.ZOMBIE_DIGGER] + ".swf";
         _loc5_[ZombiesConfig.ZOMBIE_SWF_MAP[ZombiesConfig.ZOMBIE_YETI]] = _loc6_ + ZombiesConfig.ZOMBIE_SWF_MAP[ZombiesConfig.ZOMBIE_YETI] + ".swf";
         _loc5_[ZombiesConfig.ZOMBIE_SWF_MAP[ZombiesConfig.ZOMBIE_POGO]] = _loc6_ + ZombiesConfig.ZOMBIE_SWF_MAP[ZombiesConfig.ZOMBIE_POGO] + ".swf";
         _loc5_[ZombiesConfig.ZOMBIE_SWF_MAP[ZombiesConfig.ZOMBIE_BUNGEE]] = _loc6_ + ZombiesConfig.ZOMBIE_SWF_MAP[ZombiesConfig.ZOMBIE_BUNGEE] + ".swf";
         _loc5_[ZombiesConfig.ZOMBIE_SWF_MAP[ZombiesConfig.ZOMBIE_LADDER]] = _loc6_ + ZombiesConfig.ZOMBIE_SWF_MAP[ZombiesConfig.ZOMBIE_LADDER] + ".swf";
         _loc5_[ZombiesConfig.ZOMBIE_SWF_MAP[ZombiesConfig.ZOMBIE_CATAPULT]] = _loc6_ + ZombiesConfig.ZOMBIE_SWF_MAP[ZombiesConfig.ZOMBIE_CATAPULT] + ".swf";
         _loc5_[ZombiesConfig.ZOMBIE_SWF_MAP[ZombiesConfig.ZOMBIE_DOCTOR]] = _loc6_ + ZombiesConfig.ZOMBIE_SWF_MAP[ZombiesConfig.ZOMBIE_DOCTOR] + ".swf";
         _loc5_[ZombiesConfig.ZOMBIE_SWF_MAP[ZombiesConfig.ZOMBIE_BONUS]] = _loc6_ + ZombiesConfig.ZOMBIE_SWF_MAP[ZombiesConfig.ZOMBIE_BONUS] + ".swf";
         _loc5_[ZombiesConfig.ZOMBIE_SWF_MAP[ZombiesConfig.ZOMBIE_CHARM]] = _loc6_ + ZombiesConfig.ZOMBIE_SWF_MAP[ZombiesConfig.ZOMBIE_CHARM] + ".swf";
         DataManager.getInstance().swfList = _loc5_;
         var _loc7_:Object = {};
         var _loc8_:int = 0;
         while(_loc8_ < 80)
         {
            _loc7_["item_" + _loc8_] = "image/item/item_" + _loc8_ + ".jpg";
            _loc8_++;
         }
         DataManager.getInstance().imgList = _loc7_;
         var _loc9_:SwfManager = new SwfManager();
         _loc9_.setSkin(Reflection.createSprite("loadingBarMc"));
         DataManager.getInstance().swfManager = _loc9_;
         ColorShortcuts.init();
         FilterShortcuts.init();
         CurveModifiers.init();
         DataManager.getInstance().pvzData = {};
         var _loc10_:Object = {};
         _loc10_["9"] = 500;
         _loc10_["10"] = 1000;
         _loc10_["11"] = 2000;
         DataManager.getInstance().pvzData.expLadder = _loc10_;
         var _loc11_:Object = {};
         _loc11_[0] = 0;
         _loc11_[1] = 10;
         _loc11_[2] = 20;
         DataManager.getInstance().pvzData.battleHouseLevelupBonus = _loc11_;
         DataManager.getInstance().pvzData.currentTournamentId = 1;
         var _loc12_:Array = [];
         _loc12_[1] = {
            "allowedCards":"2,12",
            "allowedZombies":[2,19],
            "amazingScore":"2180537",
            "checkMinRushTimes1":"94",
            "checkMinRushTimes2":"114",
            "checkMinRushTimes3":"155",
            "checkMinRushTimes4":"161",
            "coolDown":"3024",
            "difficultCoefficient":"18",
            "dropVase":"1",
            "dropVaseCD":"8",
            "endTime":"2011-05-24 02:59:59",
            "excellentScore":"1930162",
            "expPrize":"144",
            "expUnitScore":"200000",
            "extraPrizePercentage1":"0.150",
            "extraPrizePercentage2":"0.300",
            "extraPrizePercentage3":"0.480",
            "extraPrizePercentage4":"0.630",
            "gameDuration":"100",
            "goodScore":"1120061",
            "groupVaseQty":"50",
            "initPlant":"",
            "initSun":"1500",
            "initTomb":"0",
            "initVase":"1",
            "kingScore":"9807505",
            "levelRequired":"5",
            "minExp":"290",
            "minToken":"2900",
            "normalScore":"831114",
            "rushCoolDown":"8",
            "scene":"3",
            "specialFirstAllowWave":"16:6",
            "specialValue":null,
            "specialWeight":null,
            "startTime":"2011-05-17 03:00:00",
            "sunFrequency":"1",
            "teamTarget":"20000000",
            "tokenPrize":"1444",
            "tokenUnitScore":"200000",
            "tournamentId":"12",
            "type":"102",
            "vaseCardWeight":"4",
            "vasePlantWeight":"4",
            "vaseZombieWeight":"2",
            "weeklyBonusGems":null,
            "weeklyBonusPrizeTop":"0",
            "weeklyBonusToken":["50000","20000","10000"],
            "weeklyExp":"7000",
            "weeklyGems":"10",
            "weeklyItems":{"651":10},
            "weeklyToken":"70000"
         };
         DataManager.getInstance().pvzData.tournaments = _loc12_;
         Data.instance.time = new ServerTime();
         Data.instance.time.updateServerTime("2010-05-16 16:40:20");
         var _loc13_:Array = [];
         _loc13_.push({
            "buyId":"273",
            "coolDown":"2011-05-16 14:54:41",
            "id":"701",
            "leaveTime":"2011-05-15 19:05:06",
            "level":"3",
            "occupier":"317349248",
            "position":"160",
            "tid":"701",
            "uid":"278368436"
         });
         _loc13_.push({
            "buyId":"275",
            "coolDown":"2011-05-16 14:54:41",
            "id":"705",
            "leaveTime":"2011-05-15 19:05:06",
            "level":"3",
            "occupier":"317349248",
            "position":"165",
            "tid":"701",
            "uid":"278368436"
         });
         _loc13_.push({
            "buyId":"276",
            "coolDown":"2011-05-16 13:54:41",
            "id":"703",
            "leaveTime":"2011-05-15 19:05:06",
            "level":"3",
            "occupier":"317349248",
            "position":"170",
            "tid":"701",
            "uid":"278368436"
         });
         Data.instance.housesList = _loc13_;
         DataManager.getInstance().propItemsConfigMap = new HashMap();
         var _loc14_:Object = {
            "active":true,
            "affect":"0",
            "appFriendNumRequired":"0",
            "canBePresent":false,
            "canBeSold":false,
            "category":"7",
            "conditions":"0",
            "coolDown":"0",
            "count":"1",
            "discount":"1",
            "earlyUnlockCost":"0",
            "exp":"0",
            "featureShopOrder":"1",
            "functionId":"0",
            "greenPoints":"0",
            "groupId":"1",
            "holidays":["0"],
            "id":"701",
            "income":"0",
            "intervalDay":"0",
            "level":"1",
            "levelRequired":"1",
            "money":"600",
            "offShelfTime":"0",
            "onShelfTime":"0",
            "ownCountLimit":"1",
            "periodPurchaseCountLimit":"0",
            "randomPrize":[],
            "recommend":"0",
            "resourceId":"701",
            "sellType":"0",
            "size":"3,3",
            "special":"0",
            "status":"1",
            "subType":"1",
            "type":"4",
            "usePeriod":null
         };
         DataManager.getInstance().propItemsConfigMap.put("701",_loc14_);
         Data.instance.itemConfArr = [];
         Data.instance.itemConfArr[701] = {
            "resourceId":"701",
            "size":[3,3],
            "category":"7",
            "name":"红瓦小木屋",
            "isCompose":"0",
            "isRare":"0",
            "npcDesc":"",
            "desc":"",
            "img":"icon_house1_1",
            "bigImg":"house1_1",
            "movieClipName":"anim_house1_1",
            "resClass":"null"
         };
         DataManager.getInstance().myItemsMap = new HashMap();
         var _loc15_:Array = [];
         _loc15_.push({
            "tid":612,
            "count":11,
            "expireTime":"",
            "lastUsedTime":"",
            "buyTime":"2011-05-15 15:00:20"
         });
         _loc15_.push({
            "tid":614,
            "count":12,
            "expireTime":"",
            "lastUsedTime":"",
            "buyTime":"2011-05-15 15:00:20"
         });
         _loc15_.push({
            "tid":620,
            "count":13,
            "expireTime":"",
            "lastUsedTime":"",
            "buyTime":"2011-05-15 15:00:20"
         });
         _loc15_.push({
            "tid":622,
            "count":14,
            "expireTime":"",
            "lastUsedTime":"",
            "buyTime":"2011-05-15 15:00:20"
         });
         _loc15_.push({
            "tid":552,
            "count":15,
            "expireTime":"",
            "lastUsedTime":"",
            "buyTime":"2011-05-15 15:00:20"
         });
         DataManager.getInstance().myItemsMap.put(DataManager.ITEM_TYPE_TOOLS_TD,_loc15_);
         PropItemsManager.instace.resetConfigMap(new Object(),null);
         DataManager.getInstance().propItemsConfigMap.put("612",{
            "name":"阳光采集机",
            "desc":"阳光采集机啊啊",
            "functionId":5,
            "resourceId":612
         });
         DataManager.getInstance().propItemsConfigMap.put("614",{
            "name":"金铲子",
            "desc":"金铲子金铲子啊啊",
            "functionId":8,
            "resourceId":613
         });
         DataManager.getInstance().propItemsConfigMap.put("620",{
            "name":"水池防御车",
            "desc":"水池防御车啊啊",
            "functionId":22,
            "resourceId":617
         });
         DataManager.getInstance().propItemsConfigMap.put("622",{
            "name":"干草叉",
            "desc":"干草叉干草叉啊啊",
            "functionId":23,
            "resourceId":618
         });
         DataManager.getInstance().propItemsConfigMap.put("552",{
            "name":"经验加倍药水",
            "desc":"经验加倍药水啊啊",
            "functionId":6,
            "resourceId":552
         });
         if(DataManager.getInstance().pvzData["unlocks"] == null)
         {
            DataManager.getInstance().pvzData["unlocks"] = {};
         }
         if(DataManager.getInstance().pvzData["unlocks"][String(DataManager.UNLOCK_TYPE_CARD_SLOT)] == null)
         {
            _loc17_ = [];
            _loc17_[0] = {
               "buyTime":"",
               "count":1,
               "expireTime":null,
               "lastUsedTime":null,
               "uid":0,
               "tid":337
            };
            _loc17_[1] = {
               "buyTime":"",
               "count":1,
               "expireTime":null,
               "lastUsedTime":null,
               "uid":0,
               "tid":338
            };
            _loc17_[2] = {
               "buyTime":"",
               "count":1,
               "expireTime":null,
               "lastUsedTime":null,
               "uid":0,
               "tid":339
            };
            _loc17_[3] = {
               "buyTime":"",
               "count":1,
               "expireTime":null,
               "lastUsedTime":null,
               "uid":0,
               "tid":340
            };
            _loc17_[4] = {
               "buyTime":"",
               "count":1,
               "expireTime":null,
               "lastUsedTime":null,
               "uid":0,
               "tid":341
            };
            _loc17_[5] = {
               "buyTime":"",
               "count":1,
               "expireTime":null,
               "lastUsedTime":null,
               "uid":0,
               "tid":342
            };
            DataManager.getInstance().pvzData["unlocks"][String(DataManager.UNLOCK_TYPE_CARD_SLOT)] = _loc17_;
         }
         DataManager.getInstance().cookie = new MyCookie("test");
         PVZDataLocator.instance.missionAwardObj = {
            "exp":300,
            "expBonus":10,
            "token":1000,
            "tokenBonus":50,
            "prizes":{
               "2":1,
               "10":1
            }
         };
         EncryptTool.KEY = "aogpYPkUaX";
         DataManager.getInstance().md5FileId = "SmWcGkMmUM";
         var _loc16_:Object = {
            "active":false,
            "affect":"0",
            "appFriendNumRequired":"0",
            "canBePresent":false,
            "canBeSold":false,
            "category":"2",
            "conditions":"0",
            "coolDown":"0",
            "count":"10",
            "discount":"1",
            "earlyUnlockCost":"0",
            "exp":"0",
            "featureShopOrder":"1",
            "functionId":"0",
            "greenPoints":"0",
            "groupId":"1",
            "holidays":["0"],
            "id":"57",
            "income":"0",
            "intervalDay":"0",
            "level":"1",
            "levelRequired":"1",
            "money":"50",
            "offShelfTime":"0",
            "onShelfTime":"0",
            "ownCountLimit":"999",
            "periodPurchaseCountLimit":"0",
            "randomPrize":[],
            "recommend":"0",
            "resourceId":"57",
            "sellType":"0",
            "size":"0",
            "special":"0",
            "status":"1",
            "subType":"1",
            "type":"13",
            "usePeriod":null
         };
         DataManager.getInstance().propItemsConfigMap.put("57",_loc16_);
         DataManager.getInstance().doc = this;
         PVZDataLocator.instance.doc = this;
         PropItemsManager.instace.resetMyPropMap({});
      }
   }
}

