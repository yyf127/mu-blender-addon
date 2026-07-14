using Client.Main.Content;
using Client.Main.Controllers;
using Client.Main.Controls;
using Client.Main.Models;
using Microsoft.Xna.Framework;
using System.Threading.Tasks;

namespace Client.Main.Objects.Monsters
{
    [NpcInfo(12, "Larva")]
    public class Larva : MonsterObject
    {
        public Larva()
        {
            RenderShadow = true;
            Scale = 0.6f; // Set according to C++ Setting_Monster
        }

        public override async Task Load()
        {
            // Model Loading Type: 6 -> File Number: 6 + 1 = 7
            Model = await BMDLoader.Instance.Prepare($"Monster/Monster07.bmd");
            await base.Load();

            // Specific PlaySpeed adjustment from C++
            if (Model?.Actions != null)
            {
                const int MONSTER_ACTION_WALK = (int)MonsterActionType.Walk;
                if (MONSTER_ACTION_WALK < Model.Actions.Length && Model.Actions[MONSTER_ACTION_WALK] != null)
                {
                    Model.Actions[MONSTER_ACTION_WALK].PlaySpeed = 0.6f;
                }
            }
        }

        // Sound mapping based on C++ SetMonsterSound(MODEL_MONSTER01 + Type, 30, 31, 30, 31, 31);
        protected override void OnIdle()
        {
            base.OnIdle();
            Vector3 listenerPosition = ((WalkableWorldControl)World).Walker.Position;
            SoundController.Instance.PlayBufferWithAttenuation("Sound/mLarva1.wav", Position, listenerPosition); // Index 0 -> Sound 30
        }

        public override void OnPerformAttack(int attackType = 1)
        {
            base.OnPerformAttack(attackType);
            Vector3 listenerPosition = ((WalkableWorldControl)World).Walker.Position;
            SoundController.Instance.PlayBufferWithAttenuation("Sound/mLarva1.wav", Position, listenerPosition); // Index 2 -> Sound 30
        }

        public override void OnDeathAnimationStart()
        {
            base.OnDeathAnimationStart();
            Vector3 listenerPosition = ((WalkableWorldControl)World).Walker.Position;
            SoundController.Instance.PlayBufferWithAttenuation("Sound/mLarva2.wav", Position, listenerPosition); // Index 4 -> Sound 31
        }
    }
}