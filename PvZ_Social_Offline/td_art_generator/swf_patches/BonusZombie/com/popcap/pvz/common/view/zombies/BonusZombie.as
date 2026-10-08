package com.popcap.pvz.common.view.zombies
{
   import com.popcap.framework.core.Config;
   import com.popcap.framework.events.MyEvent;
   import com.popcap.framework.managers.DataManager;
   import com.popcap.framework.managers.SoundManager;
   import com.popcap.framework.uis.BitmapMovieClip;
   import com.popcap.pvz.common.ResourceCache;
   import com.popcap.pvz.common.conf.PVZConfig;
   import com.popcap.pvz.common.control.manager.EffectMovieManager;
   import com.popcap.pvz.common.event.PVZEventManager;
   import com.popcap.pvz.common.utils.TDTool;
   import flash.display.Sprite;
   import flash.events.Event;
   
   public class BonusZombie extends BasicZombie
   {
      
      private static var PHASE_ENTERING:int = PHASE_MAX + 1;
      
      private static var PHASE_LEAVING:int = PHASE_MAX + 2;
      
      private const _enter_start:int = 1;
      
      private const _enter_end:int = 97;
      
      private const _shake_start:int = 98;
      
      private const _shake_end:int = 170;
      
      private const _die_start:int = 171;
      
      private const _die_end:int = 193;
      
      private const _charred_start:int = 194;
      
      private const _charred_end:int = 230;
      
      private const _leave_start:int = 231;
      
      private const _leave_end:int = 275;
      
      private const _PORTAL_OPENING:int = 2;
      
      private const _ARRIVING:int = 10;
      
      private const _LAUGHING:int = 25;
      
      public var disappearCountDown:int;
      
      private var _isCharred:Boolean = false;
      
      private var _portalBmpMc:BitmapMovieClip;
      
      private var _portalContainer:Sprite;
      
      private var _headMask:Sprite;
      
      private var _bodyMask:Sprite;
      
      private var _otherMask:Sprite;
      
      public function BonusZombie(param1:int)
      {
         super(param1);
      }
      
      override protected function initData() : void
      {
         super.initData();
         this.disappearCountDown = 10 * Config.FRAME_RATE;
         this._isCharred = false;
      }
      
      override protected function initView() : void
      {
         super.initView();
         if(this._portalBmpMc == null)
         {
            this._portalBmpMc = ResourceCache.instance.createBitmapMovieClip("portal");
            this._portalContainer = new Sprite();
            this._portalContainer.addChild(this._portalBmpMc);
            this._portalContainer.x = 87;
            this._portalContainer.y = 120;
            addChildAt(this._portalContainer,0);
            this._headMask = ResourceCache.instance.getSprite("bonus_mask");
            this._bodyMask = ResourceCache.instance.getSprite("bonus_mask");
            this._otherMask = ResourceCache.instance.getSprite("bonus_mask");
            this._headMask.x = this._bodyMask.x = this._otherMask.x = 37;
            this._headMask.y = this._bodyMask.y = this._otherMask.y = 50;
            addChild(this._bodyMask);
            addChild(this._headMask);
            addChild(this._otherMask);
            bodyAni.mask = this._bodyMask;
            partAniListObj["head"].mask = this._headMask;
            partAniListObj["other"].mask = this._otherMask;
         }
         this._portalBmpMc.addFrameScript(this._portalBmpMc.totalFrame,function():void
         {
            _portalBmpMc.stop();
            removeChild(_portalContainer);
         });
         this._portalBmpMc.addFrameScript(this._PORTAL_OPENING,function():void
         {
            SoundManager.instance.createSound(PVZConfig.SOUND_PORTAL,ResourceCache.instance.getCommonResourceApp());
         });
         bodyAni.addFrameScript(this._LAUGHING,function():void
         {
            SoundManager.instance.createSound(PVZConfig.SOUND_BABY,ResourceCache.instance.getCommonResourceApp());
         });
         bodyAni.addFrameScript(this._ARRIVING,function():void
         {
            SoundManager.instance.createSound(PVZConfig.SOUND_ZOMBIE_FALLING1,ResourceCache.instance.getCommonResourceApp());
         });
      }
      
      override public function update() : void
      {
         if(currentPhase == PHASE_INIT)
         {
            this.loopPlay(this._enter_start,this._enter_end,PVZConfig.RATE36);
            bodyAni.addFrameScript(this._enter_end,this.onEnterScene);
            this._portalBmpMc.loopPlay(1,61,PVZConfig.RATE36);
            addChildAt(this._portalContainer,0);
            currentPhase = PHASE_ENTERING;
            PVZEventManager.instance.dispatchEvent(new MyEvent(PVZEventManager.NEW_BONUS_ZOMBIE,this));
         }
         if(currentPhase == PHASE_SHAKING)
         {
            --this.disappearCountDown;
            if(this.disappearCountDown == 0 && isAlive == true)
            {
               addChildAt(this._portalContainer,0);
               this._portalBmpMc.loopPlay(1,61,PVZConfig.RATE36);
               this.loopPlay(this._leave_start,this._leave_end,PVZConfig.RATE36);
               bodyAni.addFrameScript(this._leave_end,this.onLeftScene);
               currentPhase = PHASE_LEAVING;
               SoundManager.instance.createSound(PVZConfig.SOUND_HYDRAULIC,ResourceCache.instance.getCommonResourceApp());
            }
         }
      }
      
      override protected function onAddToStage(param1:Event) : void
      {
         x -= 60;
         super.onAddToStage(param1);
      }
      
      override public function reset() : void
      {
         super.reset();
         this._isCharred = false;
         this.loopPlay(this._enter_start,this._enter_end,PVZConfig.RATE36);
      }
      
      override public function injured(param1:Number, param2:int = 1, param3:int = -1) : Boolean
      {
         var _loc4_:Boolean = param2 == PVZConfig.PLANT_ATTACK_TYPE_BOMB || param2 == PVZConfig.PLANT_ATTACK_TYPE_FIRESHOOM_DIE;
         var _loc5_:Boolean = _loc4_ || param2 == PVZConfig.PLANT_ATTACK_TYPE_FIRE;
         if(this._isCharred)
         {
            return false;
         }
         if(currentPhase == PHASE_DYING)
         {
            if(_loc5_)
            {
               this.playCharred();
            }
            return false;
         }
         if(currentPhase != PHASE_ENTERING && currentPhase != PHASE_SHAKING && currentPhase != PHASE_INIT)
         {
            return false;
         }
         if(!isAlive || param1 <= 0 && !_loc4_)
         {
            return false;
         }
         if(_loc4_)
         {
            this.playCharred();
            return true;
         }
         if(param2 == PVZConfig.PLANT_ATTACK_TYPE_CLEAR)
         {
            currentPhase = PHASE_DYING;
            this.onDie();
            return true;
         }
         vo.curHP -= param1;
         if(!DataManager.getInstance().isSimpleMode)
         {
            effect.twinkle();
         }
         if(vo.curHP <= 0)
         {
            if(_loc5_)
            {
               this.playCharred();
               return true;
            }
            isAlive = false;
            this.dropHead();
            this.loopPlay(this._die_start,this._die_end,PVZConfig.RATE36);
            bodyAni.addFrameScript(this._die_end,this.onDie);
            currentPhase = PHASE_DYING;
            SoundManager.instance.createSound(PVZConfig.SOUND_DIE,ResourceCache.instance.getCommonResourceApp());
            return true;
         }
         return false;
      }
      
      private function playCharred() : void
      {
         this._isCharred = true;
         isAlive = false;
         currentPhase = PHASE_DYING;
         bodyAni.addFrameScript(this._die_end,null);
         bodyAni.addFrameScript(this._enter_end,null);
         this.loopPlay(this._charred_start,this._charred_end,PVZConfig.RATE36);
         bodyAni.addFrameScript(this._charred_end,this.onDie);
      }
      
      override protected function charredZombie() : void
      {
      }
      
      override protected function dropHead() : void
      {
         if(headAni == null)
         {
            return;
         }
         var _loc1_:int = x + headAni.x;
         var _loc2_:int = y + headAni.y;
         EffectMovieManager.createDropHeadEffect(headAni.bitmapData,_loc1_,_loc2_,isCurrentFrozen,false,null,30);
      }
      
      private function onEnterScene() : void
      {
         currentPhase = PHASE_SHAKING;
         loopPlay(this._shake_start,this._shake_end,PVZConfig.RATE36);
      }
      
      private function onLeftScene() : void
      {
         remove();
      }
      
      private function onDie() : void
      {
         remove();
      }
      
      override public function dispose() : void
      {
         super.dispose();
         if(this._portalBmpMc != null)
         {
            this._portalBmpMc.dispose();
            this._portalBmpMc = null;
         }
         TDTool.instance.removeChild(this._portalContainer);
         this._portalContainer = null;
         TDTool.instance.removeChild(this._headMask);
         this._headMask = null;
         TDTool.instance.removeChild(this._bodyMask);
         this._bodyMask = null;
         TDTool.instance.removeChild(this._otherMask);
         this._otherMask = null;
      }
   }
}

